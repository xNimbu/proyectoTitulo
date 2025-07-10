from datetime import datetime
import json
import os
import random
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http.multipartparser import MultiPartParser
from django.views.decorators.http import require_GET

from firebase_admin import auth as firebase_auth
from google.cloud import firestore

from .firebase_config import db
from .auth import firebase_login_required
from core import auth as core_auth
from core.auth import create_user
from core.models import ChatMessage
from .utils import upload_image_to_imgbb, get_post_likes
from .utils import add_notification

# --------------------------------------------------------------------------------
# Utility / Test Views
# --------------------------------------------------------------------------------


def hello_world(request):
    """
    GET /api/hello/ → prueba de escritura en Firestore
    """
    data = {
        "nombre": "Alex Caldas",
        "email": "alex@email.com",
        "proyecto": "backend con Firebase",
    }
    db.collection("usuarios").document("alex123").set(data)
    return JsonResponse({"mensaje": "Dato guardado en Firestore!"})


@firebase_login_required
def vista_protegida(request):
    """
    GET /api/protected/ → ejemplo de vista protegida
    """
    usuario = request.user_firebase
    return JsonResponse(
        {"mensaje": f'Hola {usuario["email"]}, tienes acceso!', "uid": usuario["uid"]}
    )


@csrf_exempt
@firebase_login_required
def login_google(request):
    """
    POST /api/login_google/  →  Verifica idToken, crea perfil si no existe
    Headers: Authorization: Bearer <idToken>
    Body JSON opcional: { fullName?, username?, phone?, photoURL?, role? }
    Responde también con listas de posts, friends y pets.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    # 1) Datos decodificados por el decorator
    decoded = request.user_firebase
    uid = decoded["uid"]
    email_token = decoded.get("email")
    nombre_token = decoded.get("name", "")
    photo_token = decoded.get("picture", "")

    # 2) Leer overrides desde el body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    # 3) Referencia al documento de perfil o servicio
    prof_ref = db.collection("profiles").document(uid)
    prof_snap = prof_ref.get()
    service_ref = db.collection("services").document(uid)
    service_snap = service_ref.get()
    is_service = False

    if not prof_snap.exists and service_snap.exists:
        # El usuario es un servicio registrado por un admin
        prof_ref = service_ref
        prof_snap = service_snap
        is_service = True

    # 4) Si no existe perfil, lo creamos
    if not prof_snap.exists:
        timestamp = int(datetime.utcnow().timestamp())
        code = int(f"{timestamp}{random.randint(0,9)}")

        profile_data = {
            "fullName": data.get("fullName", nombre_token),
            "username": data.get("username", ""),
            "email": data.get("email", email_token),
            "phone": data.get("phone", ""),
            "photoURL": data.get("photoURL", photo_token),
            "role": data.get("role", "user"),
            "code": data.get("code", code),
            "createdAt": datetime.utcnow(),
        }
        prof_ref.set(profile_data)
    else:
        profile_data = prof_snap.to_dict()
        code = profile_data.get("code")

    # 5) Leer sub-colecciones: posts, friends, pets
    def fetch_collection(name):
        col = prof_ref.collection(name).get()
        return [doc.to_dict() for doc in col]

    posts = fetch_collection("posts")
    if is_service:
        friends = []
        pets = []
    else:
        friends = fetch_collection("friends")
        pets = fetch_collection("pets")

    # 6) Respuesta final
    return JsonResponse(
        {
            "mensaje": "Login exitoso",
            "uid": uid,
            "role": profile_data.get("role"),
            "code": code,
            "profile": profile_data,
            "posts": posts,
            "friends": friends,
            "pets": pets,
        },
        status=200,
    )

# --------------------------------------------------------------------------------
# User Registration & Profile
# --------------------------------------------------------------------------------


@csrf_exempt
def crear_usuario(request):
    """
    POST /api/register/ → crea usuario en Firebase Auth + Firestore profile
    Body JSON: { email, password, nombre?, role? }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    # 1) Parsear JSON
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return JsonResponse({"error": "Faltan email o password"}, status=400)

    nombre = data.get("nombre", "")
    role = data.get("role", "user")

    try:
        # 2) Crear usuario en Auth
        user_record = create_user(
            email=email,
            password=password,
            display_name=nombre,
        )

        # 3) Generar código numérico único
        timestamp = int(datetime.utcnow().timestamp())
        code = int(f"{timestamp}{random.randint(0,9)}")

        # 4) Guardar perfil en Firestore
        profile_data = {
            "fullName": nombre,
            "email": email,
            "role": role,
            "code": code,
            "createdAt": datetime.utcnow(),  # o firestore.SERVER_TIMESTAMP()
        }
        db.collection("profiles").document(user_record.uid).set(profile_data)

        # 5) Responder al cliente
        return JsonResponse(
            {
                "mensaje": "Usuario creado",
                "uid": user_record.uid,
                "role": role,
                "code": code,
            },
            status=201,
        )

    except Exception as e:
        # Aquí puedes mapear errores específicos de Firebase si quieres
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@firebase_login_required
def profile(request):
    """
    GET  /api/profile/       → perfil propio + pets + posts + friends
    POST /api/profile/       → crea/actualiza perfil propio
    """
    uid = request.user_firebase["uid"]
    email = request.user_firebase["email"]
    doc_ref = db.collection("profiles").document(uid)
    service_ref = db.collection("services").document(uid)
    service_snap = service_ref.get()
    if not doc_ref.get().exists and service_snap.exists:
        doc_ref = service_ref

    if request.method == "GET":
        snap = doc_ref.get()
        if not snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)
        data = snap.to_dict()

        role = data.get("role", "user")
        profile_data = {
            "fullName": data.get("fullName"),
            "username": data.get("username"),
            "email": data.get("email", email),
            "phone": data.get("phone"),
            "photoURL": data.get("photoURL"),
            "role": role,
            "code": data.get("code"),
        }

        # Mascotas solo para usuarios normales
        pets = []
        if role != "service":
            for pet_snap in doc_ref.collection("pets").stream():
                pet = pet_snap.to_dict()
                pet["id"] = pet_snap.id
                pets.append(pet)
        profile_data["pets"] = pets

        # Publicaciones
        posts = []
        for post_snap in (
            doc_ref.collection("posts")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .stream()
        ):
            p = post_snap.to_dict()
            p["id"] = post_snap.id
            p["timestamp"] = p.get("timestamp").isoformat() if p.get("timestamp") else None

            # ——> fetch de comentarios:
            comments = []
            for c_snap in db.collection("posts").document(p["id"]).collection("comments").order_by("timestamp").stream():
                c = c_snap.to_dict()
                c["id"] = c_snap.id
                comments.append(c)
            p["comments"] = comments

            likes = get_post_likes(p["id"])
            p["likes"] = likes
            p["likesCount"] = len(likes)

            posts.append(p)
        profile_data["posts"] = posts

        # Amigos solo para usuarios normales
        friends = []
        if role != "service":
            for friend_snap in doc_ref.collection("friends").stream():
                f = friend_snap.to_dict()
                friends.append(
                    {
                        "uid": friend_snap.id,
                        "username": f.get("username", ""),
                        "avatar": f.get("avatar", ""),
                        "addedAt": (
                            f.get("addedAt").isoformat() if f.get("addedAt") else None
                        ),
                    }
                )
        profile_data["friends"] = friends

        return JsonResponse(profile_data)

    if request.method == "POST":
        # 1) Leemos los campos de form-data
        fullName = request.POST.get("fullName")
        username = request.POST.get("username")
        email = request.POST.get("email")
        phone = request.POST.get("phone")

        # 2) Subimos la foto si viene usando imgbb
        image_file = request.FILES.get("image")
        photoURL = upload_image_to_imgbb(image_file)

        # 3) Armamos el dict de actualización
        update = {}
        if fullName:
            update["fullName"] = fullName
        if username:
            update["username"] = username
        if email:
            update["email"] = email
        if phone:
            update["phone"] = phone
        if photoURL:
            update["photoURL"] = photoURL

        if not update:
            return JsonResponse({"error": "Sin datos para actualizar"}, status=400)

        # 4) Hacemos el merge en Firestore
        doc_ref.set(update, merge=True)

        # 5) Respondemos con la URL nueva y mensaje
        return JsonResponse(
            {
                "mensaje": "Perfil guardado",
                "photoURL": photoURL,  # opcional, para que el cliente la use
            }
        )

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def profile_detail(request, uid):
    """
    GET /api/profile/<uid>/ → perfil público de cualquier usuario
    """
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    doc_ref = db.collection("profiles").document(uid)
    snap = doc_ref.get()
    if not snap.exists:
        service_ref = db.collection("services").document(uid)
        snap = service_ref.get()
        if not snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)
        doc_ref = service_ref
    data = snap.to_dict()

    role = data.get("role", "user")
    profile_data = {
        "fullName": data.get("fullName"),
        "username": data.get("username"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "photoURL": data.get("photoURL"),
        "role": role,
        "code": data.get("code"),
    }

    # Mascotas
    if role != "service":
        profile_data["pets"] = [
            dict(**pet_snap.to_dict(), id=pet_snap.id)
            for pet_snap in doc_ref.collection("pets").stream()
        ]
    else:
        profile_data["pets"] = []

    # Publicaciones
    posts = []
    for post_snap in (
        doc_ref.collection("posts")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .stream()
    ):
        p = post_snap.to_dict()
        p["id"] = post_snap.id
        p["timestamp"] = p.get("timestamp").isoformat() if p.get("timestamp") else None
        likes = get_post_likes(p["id"])
        p["likes"] = likes
        p["likesCount"] = len(likes)
        posts.append(p)
    profile_data["posts"] = posts

    # Amigos
    if role != "service":
        profile_data["friends"] = [
            {
                "uid": f_snap.id,
                "username": f.get("username", ""),
                "avatar": f.get("avatar", ""),
                "addedAt": f.get("addedAt").isoformat() if f.get("addedAt") else None,
            }
            for f_snap in doc_ref.collection("friends").stream()
            for f in [f_snap.to_dict()]
        ]
    else:
        profile_data["friends"] = []

    return JsonResponse(profile_data)


@csrf_exempt
@firebase_login_required
def profile_by_username(request, username):
    """Obtiene el perfil público de un usuario por su nombre de usuario."""
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    query = (
        db.collection("profiles")
        .where("username", "==", username)
        .limit(1)
        .stream()
    )

    uid = None
    for snap in query:
        uid = snap.id
        break

    if not uid:
        # Buscar en servicios
        query = (
            db.collection("services")
            .where("username", "==", username)
            .limit(1)
            .stream()
        )
        for snap in query:
            uid = snap.id
            break
        if not uid:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)

    # Reutilizar la lógica de `profile_detail`
    return profile_detail(request, uid)


@csrf_exempt
def profile_list(request):
    """
    GET /api/profile_list/ → lista pública de perfiles, admite ?q= para filtrar por username
    """
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    q = request.GET.get("q", "").lower()
    perfiles = []
    for doc in db.collection("profiles").stream():
        data = doc.to_dict()
        username = data.get("username", "")
        if q and q not in username.lower():
            continue
        perfiles.append(
            {"uid": doc.id, "username": username, "avatar": data.get("photoURL", "")}
        )
    return JsonResponse(perfiles, safe=False)


# --------------------------------------------------------------------------------
# Pets CRUD
# --------------------------------------------------------------------------------


@csrf_exempt
@firebase_login_required
def pets(request):
    """
    GET  /api/profile/pets/ → lista mascotas
    POST /api/profile/pets/ → crea mascota
    """
    uid = request.user_firebase["uid"]
    col = db.collection("profiles").document(uid).collection("pets")

    if request.method == "GET":
        pets_list = []
        for snap in col.stream():
            pet = snap.to_dict()
            pet["id"] = snap.id
            pets_list.append(pet)
        return JsonResponse({"pets": pets_list})

    elif request.method == "POST":
        image_file = request.FILES.get("image")
        photoURL = upload_image_to_imgbb(image_file) or ""
        data = request.POST.dict()
        if not data:
            try:
                data = json.loads(request.body or "{}")
            except json.JSONDecodeError:
                data = {}
        nueva = {
            "name": data.get("name"),
            "breed": data.get("breed"),
            "age": data.get("age"),
            "type": data.get("type"),
            "photoURL": photoURL,
        }
        _, doc_ref = col.add(nueva)
        return JsonResponse({"mensaje": "Mascota creada", "id": doc_ref.id}, status=201)

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def pet_detail(request, pet_id):
    """
    PUT    /api/profile/pets/<pet_id>/ → actualiza mascota
    DELETE /api/profile/pets/<pet_id>/ → elimina mascota
    """
    uid = request.user_firebase["uid"]
    doc = db.collection("profiles").document(uid).collection("pets").document(pet_id)

    if request.method == "PUT":
        data = request.POST.dict()
        if not data:
            try:
                data = json.loads(request.body or "{}")
            except json.JSONDecodeError:
                data = {}
        image_file = request.FILES.get("image")
        if image_file:
            photoURL = upload_image_to_imgbb(image_file) or ""
            if photoURL:
                data["photoURL"] = photoURL
        if not data:
            return JsonResponse({"error": "Sin datos para actualizar"}, status=400)
        doc.update(data)
        return JsonResponse({"mensaje": "Mascota actualizada"})

    elif request.method == "DELETE":
        doc.delete()
        return JsonResponse({"mensaje": "Mascota eliminada"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


# --------------------------------------------------------------------------------
# Posts & Comments CRUD
# --------------------------------------------------------------------------------


@csrf_exempt
@firebase_login_required
def user_posts(request):
    """
    GET  /api/profile/posts/ → lista posts del usuario
    POST /api/profile/posts/ → crea post con imagen opcional
    """
    uid = request.user_firebase["uid"]
    col = db.collection("profiles").document(uid).collection("posts")

    if request.method == "GET":
        posts = []
        for snap in col.order_by("timestamp", direction=firestore.Query.DESCENDING).stream():
            post = snap.to_dict()
            post_id = snap.id
            post["id"] = post_id

            # ——> aquí obtenemos sus comentarios:
            comments = []
            # Fíjate que tu vista de comments usa la colección global "posts"
            comments_col = db.collection("posts").document(post_id).collection("comments")
            for c_snap in comments_col.order_by("timestamp").stream():
                c = c_snap.to_dict()
                c["id"] = c_snap.id
                comments.append(c)
            post["comments"] = comments

            likes = get_post_likes(post_id)
            post["likes"] = likes
            post["likesCount"] = len(likes)

            posts.append(post)

        return JsonResponse({"posts": posts})

    elif request.method == "POST":
        content = request.POST.get("content", "")
        image_file = request.FILES.get("image")
        photoURL = upload_image_to_imgbb(image_file) or ""
        pet_id = request.POST.get("pet_id")
        new_post = {
            "content": content,
            "photoURL": photoURL,
            "timestamp": datetime.utcnow(),
        }
        if pet_id:
            new_post["pet_id"] = pet_id
        _, doc_ref = col.add(new_post)
        # crea documento global para comentarios/likes
        db.collection("posts").document(doc_ref.id).set({"owner": uid}, merge=True)
        return JsonResponse({"mensaje": "Post creado", "id": doc_ref.id}, status=201)

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def user_post_detail(request, post_id):
    """
    PUT    /api/profile/posts/<post_id>/ → actualiza post
    DELETE /api/profile/posts/<post_id>/ → elimina post
    """
    uid = request.user_firebase["uid"]
    doc = db.collection("profiles").document(uid).collection("posts").document(post_id)

    if request.method == "PUT":
        data = json.loads(request.body)
        snap = doc.get()
        if not snap.exists:
            return JsonResponse({"error": "Post no encontrado"}, status=404)
        old = snap.to_dict()
        doc.update(
            {
            "content": data.get("content", old.get("content")),
            "photoURL": data.get("photoURL", old.get("photoURL")),
            "timestamp": datetime.utcnow(),
            }
        )
        # Si el post tiene pet_id, obtener datos de la mascota
        pet_data = None
        pet_id = old.get("pet_id") or data.get("pet_id")
        if pet_id:
            pet_ref = db.collection("profiles").document(uid).collection("pets").document(pet_id)
            pet_snap = pet_ref.get()
            if pet_snap.exists:
                pet = pet_snap.to_dict()
                pet["id"] = pet_snap.id
                pet_data = pet
        response = {"mensaje": "Post actualizado"}
        if pet_data:
            response["pet"] = pet_data
        return JsonResponse(response)

    elif request.method == "DELETE":
        doc.delete()
        db.collection("posts").document(post_id).delete()
        return JsonResponse({"mensaje": "Post eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def comments(request, post_id):
    """
    GET  /api/profile/posts/<post_id>/comments/ → lista comentarios
    POST /api/profile/posts/<post_id>/comments/ → crea comentario
    """
    col = db.collection("posts").document(post_id).collection("comments")

    if request.method == "GET":
        comments = []
        for snap in col.order_by("timestamp").stream():
            c = snap.to_dict()
            c["id"] = snap.id
            comments.append(c)
        return JsonResponse({"comments": comments})

    elif request.method == "POST":
        user = request.user_firebase
        data = json.loads(request.body)
        new_comment = {
            "userId": user["uid"],
            "message": data.get("message"),
            "timestamp": datetime.utcnow(),
        }
        _, doc_ref = col.add(new_comment)
        post_snap = db.collection("posts").document(post_id).get()
        owner = post_snap.to_dict().get("owner") if post_snap.exists else None
        if owner and owner != user["uid"]:
            add_notification(
                owner,
                f"{user['email']} coment\u00f3 tu publicaci\u00f3n",
                "comment",
                {"postId": post_id},
            )
        return JsonResponse(
            {"mensaje": "Comentario agregado", "id": doc_ref.id}, status=201
        )

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def comment_detail(request, post_id, comment_id):
    """
    PUT    /api/posts/<post_id>/comments/<comment_id>/ → actualiza comentario
    DELETE /api/posts/<post_id>/comments/<comment_id>/ → elimina comentario
    """
    ref = (
        db.collection("posts")
        .document(post_id)
        .collection("comments")
        .document(comment_id)
    )

    # Traer el comentario actual
    snapshot = ref.get()
    if not snapshot.exists:
        return JsonResponse({"error": "Comentario no encontrado"}, status=404)

    comment_data = snapshot.to_dict()
    user_uid = request.user_firebase["uid"]

    # Verifica si el comentario le pertenece al usuario actual
    if comment_data.get("userId") != user_uid:
        return JsonResponse({"error": "No tienes permiso para modificar este comentario"}, status=403)

    if request.method == "PUT":
        data = json.loads(request.body)
        ref.update(
            {
                "message": data.get("message"),
                "timestamp": datetime.utcnow(),
            }
        )
        return JsonResponse({"mensaje": "Comentario actualizado"})

    elif request.method == "DELETE":
        ref.delete()
        return JsonResponse({"mensaje": "Comentario eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def likes(request, post_id):
    """Gestiona likes de un post."""
    col = db.collection("posts").document(post_id).collection("likes")

    if request.method == "GET":
        likes = get_post_likes(post_id)
        return JsonResponse({"count": len(likes), "likes": likes})

    elif request.method == "POST":
        user = request.user_firebase
        uid = user["uid"]
        profile = db.collection("profiles").document(uid).get()
        username = ""
        if profile.exists:
            username = profile.to_dict().get("username", "")
        like_ref = col.document(uid)
        if like_ref.get().exists:
            like_ref.delete()
            liked = False
        else:
            like_ref.set({"username": username})
            liked = True
            post_snap = db.collection("posts").document(post_id).get()
            owner = post_snap.to_dict().get("owner") if post_snap.exists else None
            if owner and owner != uid:
                add_notification(
                    owner,
                    f"{username or user['email']} le dio like a tu publicaci\u00f3n",
                    "like",
                    {"postId": post_id},
                )
        likes = get_post_likes(post_id)
        return JsonResponse({"liked": liked, "count": len(likes), "likes": likes})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def friends_posts(request):
    """Lista los posts propios y los de todos los amigos mezclados."""

    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    uid = request.user_firebase["uid"]
    profile_ref = db.collection("profiles").document(uid)

    def collect_posts(user_uid):
        """Devuelve la lista de posts de un usuario con owner, comments y likes."""
        profile = db.collection("profiles").document(user_uid).get().to_dict() or {}
        owner_info = {
            "uid": user_uid,
            "username": profile.get("username", ""),
            "avatar": profile.get("photoURL", ""),
        }

        resultados = []
        col = (
            db.collection("profiles")
            .document(user_uid)
            .collection("posts")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
        )
        for snap in col.stream():
            post = snap.to_dict()
            post_id = snap.id
            post["id"] = post_id
            post["owner"] = owner_info

            comments = []
            comments_col = (
                db.collection("posts")
                .document(post_id)
                .collection("comments")
            )
            for c_snap in comments_col.order_by("timestamp").stream():
                c = c_snap.to_dict()
                c["id"] = c_snap.id
                comments.append(c)
            post["comments"] = comments

            likes = get_post_likes(post_id)
            post["likes"] = likes
            post["likesCount"] = len(likes)

            resultados.append(post)
        return resultados

    posts = collect_posts(uid)

    for friend_snap in profile_ref.collection("friends").stream():
        posts.extend(collect_posts(friend_snap.id))

    posts.sort(key=lambda p: p.get("timestamp"), reverse=True)
    for p in posts:
        ts = p.get("timestamp")
        if ts:
            p["timestamp"] = ts.isoformat()

    return JsonResponse({"posts": posts})


@require_GET
@firebase_login_required
def posts_by_user(request, user_uid):
    """Lista los posts públicos de un usuario específico."""

    doc_ref = db.collection("profiles").document(user_uid)
    snap = doc_ref.get()
    if not snap.exists:
        doc_ref = db.collection("services").document(user_uid)
        snap = doc_ref.get()
        if not snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)

    resultados = []
    col = (
        doc_ref
        .collection("posts")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
    )
    for snap in col.stream():
        post = snap.to_dict()
        post_id = snap.id
        post["id"] = post_id

        comments = []
        comments_col = (
            db.collection("posts")
            .document(post_id)
            .collection("comments")
        )
        for c_snap in comments_col.order_by("timestamp").stream():
            c = c_snap.to_dict()
            c["id"] = c_snap.id
            comments.append(c)
        post["comments"] = comments

        likes = get_post_likes(post_id)
        post["likes"] = likes
        post["likesCount"] = len(likes)

        ts = post.get("timestamp")
        if ts:
            post["timestamp"] = ts.isoformat()

        resultados.append(post)

    return JsonResponse({"posts": resultados})


# --------------------------------------------------------------------------------
# Friends CRUD
# --------------------------------------------------------------------------------


@csrf_exempt
@firebase_login_required
def friends(request):
    """
    GET  /api/profile/friends/ → listar amigos del usuario
    POST /api/profile/friends/ → agregar amigo bidireccional
    """
    uid = request.user_firebase["uid"]
    profile_ref = db.collection("profiles").document(uid)
    col_me = profile_ref.collection("friends")

    if request.method == "GET":
        items = []
        for snap in col_me.stream():
            d = snap.to_dict()
            items.append(
                {
                    "uid": snap.id,
                    "username": d.get("username", ""),
                    "avatar": d.get("avatar", ""),
                    "addedAt": d.get("addedAt"),
                }
            )
        return JsonResponse({"friends": items})

    elif request.method == "POST":
        data = json.loads(request.body)
        target_uid = data.get("uid")
        if not target_uid or target_uid == uid:
            return JsonResponse({"error": "UID inválido"}, status=400)

        # Verifica perfil destino
        other_ref = db.collection("profiles").document(target_uid)
        other_snap = other_ref.get()
        if not other_snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)

        # Registro A→B
        other_data = other_snap.to_dict()
        record_me = {
            "username": other_data.get("username", ""),
            "avatar": other_data.get("photoURL", ""),
            "addedAt": firestore.SERVER_TIMESTAMP,
        }
        col_me.document(target_uid).set(record_me)

        # Registro B→A
        me_snap = profile_ref.get()
        me_data = me_snap.to_dict() or {}
        record_other = {
            "username": me_data.get("username", ""),
            "avatar": me_data.get("photoURL", ""),
            "addedAt": firestore.SERVER_TIMESTAMP,
        }
        other_ref.collection("friends").document(uid).set(record_other)

        add_notification(
            target_uid,
            f"{me_data.get('username', '') or uid} te agreg\u00f3 como amigo",
            "friend",
            {"uid": uid},
        )

        return JsonResponse(
            {
                "mensaje": "Amigo agregado bidireccionalmente",
                "you": uid,
                "friend": target_uid,
            },
            status=201,
        )

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def friend_detail(request, friend_uid):
    """
    GET    /api/profile/friends/<friend_uid>/ → ver perfil de ese amigo
    DELETE /api/profile/friends/<friend_uid>/ → eliminar amigo unidireccional
    """
    uid = request.user_firebase["uid"]
    friend_ref = db.collection("profiles").document(friend_uid)
    friend_snap = friend_ref.get()
    if not friend_snap.exists:
        return JsonResponse({"error": "Perfil no encontrado"}, status=404)

    if request.method == "GET":
        return profile_detail(request, friend_uid)

    elif request.method == "DELETE":
        rel_ref = (
            db.collection("profiles")
            .document(uid)
            .collection("friends")
            .document(friend_uid)
        )
        if not rel_ref.get().exists:
            return JsonResponse({"error": "Amigo no encontrado"}, status=404)
        rel_ref.delete()
        return JsonResponse({"mensaje": "Amigo eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


# --------------------------------------------------------------------------------
# Chat History
# --------------------------------------------------------------------------------


@require_GET
@firebase_login_required
def chat_history(request, room_name):
    """Devuelve historial y marca mensajes como leídos por el usuario."""
    uid = request.user_firebase["uid"]
    msgs = ChatMessage.objects.filter(room=room_name).order_by("id")
    data = []
    for msg in msgs:
        if uid not in msg.read_by:
            msg.read_by.append(uid)
            msg.save(update_fields=["read_by"])
        data.append({"user": msg.user, "message": msg.message})
    return JsonResponse(data, safe=False)


@csrf_exempt
@firebase_login_required
def relations(request, other_uid=None):
    """
    GET    /api/profile/relations/          → lista amigos o seguidores según role
    POST   /api/profile/relations/          → agrega
    DELETE /api/profile/relations/<other_uid>/    → elimina
    """
    uid = request.user_firebase["uid"]
    profile_ref = db.collection("profiles").document(uid)
    me_data = profile_ref.get().to_dict() or {}
    role = me_data.get("role", "user")
    subcol = "friends" if role in ("user", "admin") else "followers"
    col = profile_ref.collection(subcol)

    if request.method == "GET":
        items = []
        for snap in col.stream():
            d = snap.to_dict()
            items.append({**d, "uid": snap.id})
        return JsonResponse({subcol: items})

    elif request.method == "POST":
        data = json.loads(request.body)
        target_uid = data.get("uid")
        if not target_uid or target_uid == uid:
            return JsonResponse({"error": "UID inválido"}, status=400)
        other_snap = db.collection("profiles").document(target_uid).get()
        if not other_snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)
        other = other_snap.to_dict()
        record = {
            "username": other.get("username", ""),
            "avatar": other.get("photoURL", ""),
            "addedAt": firestore.SERVER_TIMESTAMP,
        }
        col.document(target_uid).set(record)
        return JsonResponse(
            {"mensaje": f"{subcol[:-1].capitalize()} agregado", "uid": target_uid},
            status=201,
        )

    elif request.method == "DELETE" and other_uid:
        ref = col.document(other_uid)
        if not ref.get().exists:
            return JsonResponse(
                {"error": f"{subcol[:-1].capitalize()} no encontrado"}, status=404
            )
        ref.delete()
        return JsonResponse({"mensaje": f"{subcol[:-1].capitalize()} eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def notifications(request):
    """Lista y crea notificaciones del usuario (solo GET)."""
    uid = request.user_firebase["uid"]
    col = db.collection("profiles").document(uid).collection("notifications")

    if request.method == "GET":
        items = []
        for snap in col.order_by("timestamp", direction=firestore.Query.DESCENDING).stream():
            d = snap.to_dict()
            d["id"] = snap.id
            ts = d.get("timestamp")
            if ts:
                d["timestamp"] = ts.isoformat()
            items.append(d)
        return JsonResponse({"notifications": items})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def notification_detail(request, notification_id):
    """Marca una notificación como leída o la elimina."""
    uid = request.user_firebase["uid"]
    doc = db.collection("profiles").document(uid).collection("notifications").document(notification_id)

    if request.method == "PATCH":
        doc.update({"read": True})
        return JsonResponse({"mensaje": "Notificación leída"})

    elif request.method == "DELETE":
        doc.delete()
        return JsonResponse({"mensaje": "Notificación eliminada"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@firebase_login_required
def chat_unread_count(request, room_name):
    """Devuelve cantidad de mensajes no leídos en una sala."""
    uid = request.user_firebase["uid"]
    from django.db.models import Q
    count = ChatMessage.objects.filter(room=room_name).exclude(read_by__contains=[uid]).count()
    return JsonResponse({"unread": count})


# ------------------------------------------------------------------------------
# Service Profiles
# ------------------------------------------------------------------------------


@csrf_exempt
@firebase_login_required
def create_service_profile(request):
    """Crea un perfil de empresa o servicio (solo admins)."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    admin_uid = request.user_firebase["uid"]
    admin_ref = db.collection("profiles").document(admin_uid).get()
    if not admin_ref.exists or admin_ref.to_dict().get("role") != "admin":
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    email = data.get("email")
    password = data.get("password")
    business_name = data.get("businessName") or data.get("razonSocial")
    services_offered = data.get("services", [])
    contact = data.get("contact", {})

    if not email or not password or not business_name:
        return JsonResponse({"error": "Faltan datos requeridos"}, status=400)

    try:
        user_record = create_user(email=email, password=password, display_name=business_name)

        timestamp = int(datetime.utcnow().timestamp())
        code = int(f"{timestamp}{random.randint(0,9)}")

        profile_data = {
            "businessEmail": email,
            "businessName": business_name,
            "services": services_offered,
            "contact": contact,
            "tempPassword": password,
            "role": "service",
            "code": code,
            "createdAt": datetime.utcnow(),
            "username": data.get("username", ""),
        }

        db.collection("services").document(user_record.uid).set(profile_data)
        return JsonResponse({"mensaje": "Servicio creado", "uid": user_record.uid, "code": code}, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def services_list(request):
    """Lista todos los perfiles de servicio."""
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    q = request.GET.get("q", "").lower()
    servicios = []
    for snap in db.collection("services").stream():
        d = snap.to_dict()
        if q:
            tipos = " ".join(d.get("services", [])).lower()
            if q not in tipos:
                continue
        servicios.append({"uid": snap.id, "businessName": d.get("businessName"), "services": d.get("services", [])})
    return JsonResponse(servicios, safe=False)


@csrf_exempt
@firebase_login_required
def contact_service(request):
    """Permite a un usuario enviar un mensaje a un servicio."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    from_uid = request.user_firebase["uid"]

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    service_uid = data.get("serviceUid")
    message = data.get("message")
    if not service_uid or not message:
        return JsonResponse({"error": "Faltan datos"}, status=400)

    service_ref = db.collection("services").document(service_uid)
    if not service_ref.get().exists:
        return JsonResponse({"error": "Servicio no encontrado"}, status=404)

    msg = {
        "fromUser": from_uid,
        "serviceUid": service_uid,
        "message": message,
        "timestamp": datetime.utcnow(),
    }
    service_ref.collection("messages").add(msg)
    return JsonResponse({"mensaje": "Mensaje enviado"}, status=201)
