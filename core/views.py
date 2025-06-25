from datetime import datetime
import json
import os
import random
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from firebase_admin import auth as firebase_auth
from google.cloud import firestore

from .firebase_config import db
from .auth import firebase_login_required
from core import auth
from core.models import ChatMessage

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
    return JsonResponse({
        "mensaje": f'Hola {usuario["email"]}, tienes acceso!',
        "uid": usuario["uid"]
    })

# --------------------------------------------------------------------------------
# User Registration & Profile
# --------------------------------------------------------------------------------

@csrf_exempt
def crear_usuario(request):
    """
    POST /api/register/ → crea usuario en Firebase Auth + Firestore profile
    Body: { email, password, nombre?, role? }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        data = json.loads(request.body)
        email = data["email"]
        password = data["password"]
        nombre = data.get("nombre", "")
        role = data.get("role", "user")

        # Crear usuario en Auth
        user = auth.create_user(
            email=email,
            password=password,
            display_name=nombre
        )

        # Generar código numérico único
        timestamp = int(datetime.utcnow().timestamp())
        code = int(f"{timestamp}{random.randint(0,9)}")

        # Guardar perfil en Firestore
        db.collection("profiles").document(user.uid).set({
            "fullName": nombre,
            "email": email,
            "role": role,
            "code": code,
            "createdAt": datetime.utcnow(),
        })

        return JsonResponse({
            "mensaje": "Usuario creado",
            "uid": user.uid,
            "role": role,
            "code": code,
        }, status=201)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@firebase_login_required
def profile(request):
    """
    GET  /api/profile/ → perfil + pets + posts + role/code
    POST /api/profile/ → crea/actualiza perfil
    """
    uid = request.user_firebase["uid"]
    email = request.user_firebase["email"]
    doc_ref = db.collection("profiles").document(uid)

    if request.method == "GET":
        snap = doc_ref.get()
        if not snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)
        data = snap.to_dict()

        # Campos básicos
        profile_data = {
            "fullName": data.get("fullName"),
            "username": data.get("username"),
            "email": data.get("email", email),
            "phone": data.get("phone"),
            "photoURL": data.get("photoURL"),
            "role": data.get("role", "user"),
            "code": data.get("code"),
        }

        # Mascotas
        pets = []
        for pet_snap in doc_ref.collection("pets").stream():
            pet = pet_snap.to_dict()
            pet["id"] = pet_snap.id
            pets.append(pet)
        profile_data["pets"] = pets

        # Publicaciones
        posts = []
        for post_snap in doc_ref.collection("posts").order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        ).stream():
            post = post_snap.to_dict()
            post["id"] = post_snap.id
            posts.append(post)
        profile_data["posts"] = posts

        friends = []
        for friend_snap in doc_ref.collection("friends").stream():
            f = friend_snap.to_dict()
            friends.append({
                "uid": friend_snap.id,
                "username": f.get("username", ""),
                "avatar": f.get("avatar", ""),
                "addedAt": f.get("addedAt"),
            })
        profile_data["friends"] = friends

        return JsonResponse(profile_data)

    elif request.method in ("POST", "PUT"):
        body = json.loads(request.body)
        perfil = {
            "fullName": body.get("fullName"),
            "username": body.get("username"),
            "phone": body.get("phone"),
            "role": body.get("role"),
            "photoURL": body.get("photoURL"),
        }
        doc_ref.set(perfil, merge=True)
        return JsonResponse({"mensaje": "Perfil guardado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)

@csrf_exempt
def profile_list(request):
    q = request.GET.get('q','').lower()
    perfiles = []
    for doc in db.collection("profiles").stream():
        data = doc.to_dict()
        username = data.get("username","")
        if q and q not in username.lower():
            continue
        perfiles.append({
            "uid": doc.id,
            "username": username,
            "avatar": data.get("photoURL","")
        })
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
        data = json.loads(request.body)
        nueva = {
            "name": data["name"],
            "breed": data.get("breed"),
            "age": data.get("age"),
            "type": data.get("type"),
            "photoURL": data.get("photoURL"),
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
        data = json.loads(request.body)
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
            post["id"] = snap.id
            posts.append(post)
        return JsonResponse({"posts": posts})

    elif request.method == "POST":
        content = request.POST.get("content", "")
        photoURL = ""
        image_file = request.FILES.get("image")
        if image_file:
            api_key = os.getenv("IMGBB_API_KEY")
            resp = requests.post(
                "https://api.imgbb.com/1/upload",
                params={"key": api_key},
                files={"image": image_file.read()}
            )
            if resp.status_code == 200:
                photoURL = resp.json()["data"]["url"]
        new_post = {
            "content": content,
            "photoURL": photoURL,
            "timestamp": datetime.utcnow(),
        }
        _, doc_ref = col.add(new_post)
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
        doc.update({
            "content": data.get("content", old.get("content")),
            "photoURL": data.get("photoURL", old.get("photoURL")),
            "timestamp": datetime.utcnow(),
        })
        return JsonResponse({"mensaje": "Post actualizado"})

    elif request.method == "DELETE":
        doc.delete()
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
            "username": user["email"],
            "message": data.get("message"),
            "timestamp": datetime.utcnow(),
        }
        _, doc_ref = col.add(new_comment)
        return JsonResponse({"mensaje": "Comentario agregado", "id": doc_ref.id}, status=201)

    return JsonResponse({"error": "Método no permitido"}, status=405)

@csrf_exempt
@firebase_login_required
def comment_detail(request, post_id, comment_id):
    """
    PUT    /api/posts/<post_id>/comments/<comment_id>/ → actualiza comentario
    DELETE /api/posts/<post_id>/comments/<comment_id>/ → elimina comentario
    """
    ref = db.collection("posts").document(post_id).collection("comments").document(comment_id)

    if request.method == "PUT":
        data = json.loads(request.body)
        ref.update({
            "message": data.get("message"),
            "timestamp": datetime.utcnow(),
        })
        return JsonResponse({"mensaje": "Comentario actualizado"})
    elif request.method == "DELETE":
        ref.delete()
        return JsonResponse({"mensaje": "Comentario eliminado"})
    return JsonResponse({"error": "Método no permitido"}, status=405)

# --------------------------------------------------------------------------------
# Friends CRUD
# --------------------------------------------------------------------------------

@csrf_exempt
@firebase_login_required
def friends(request):
    """
    GET  /api/profile/friends/               → Listar amigos
    POST /api/profile/friends/               → Agregar un amigo
    """
    uid = request.user_firebase["uid"]
    profile_ref = db.collection("profiles").document(uid)
    col = profile_ref.collection("friends")

    if request.method == "GET":
        items = []
        for snap in col.stream():
            d = snap.to_dict()
            items.append({
                "uid": snap.id,
                "username": d.get("username", ""),
                "avatar": d.get("avatar", ""),
                "addedAt": d.get("addedAt"),
            })
        return JsonResponse({"friends": items})

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
        return JsonResponse({"mensaje": "Amigo agregado", "uid": target_uid}, status=201)

    return JsonResponse({"error": "Método no permitido"}, status=405)

@csrf_exempt
@firebase_login_required
def friend_detail(request, friend_uid):
    """
    DELETE /api/profile/friends/<friend_uid>/ → Eliminar amigo
    """
    if request.method != "DELETE":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    uid = request.user_firebase["uid"]
    ref = db.collection("profiles").document(uid).collection("friends").document(friend_uid)

    if not ref.get().exists:
        return JsonResponse({"error": "Amigo no encontrado"}, status=404)

    ref.delete()
    return JsonResponse({"mensaje": "Amigo eliminado"})

# --------------------------------------------------------------------------------
# Followers/Friends Relations CRUD
# --------------------------------------------------------------------------------

@csrf_exempt
@firebase_login_required
def relations(request, other_uid=None):
    """
    GET    /api/profile/relations/          → lista amigos o seguidores según role
    POST   /api/profile/relations/          → agrega
    DELETE /api/profile/relations/<uid>/    → elimina
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
            d["uid"] = snap.id
            items.append(d)
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
        return JsonResponse({"mensaje": f"{subcol[:-1].capitalize()} agregado", "uid": target_uid}, status=201)

    elif request.method == "DELETE" and other_uid:
        ref = col.document(other_uid)
        if not ref.get().exists:
            return JsonResponse({"error": f"{subcol[:-1].capitalize()} no encontrado"}, status=404)
        ref.delete()
        return JsonResponse({"mensaje": f"{subcol[:-1].capitalize()} eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)

# --------------------------------------------------------------------------------
# Chat History
# --------------------------------------------------------------------------------

def chat_history(request, room):
    """
    GET /api/chat/<room>/history/ → historial de chat desde base SQL
    """
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    mensajes = ChatMessage.objects.filter(room=room)
    data = [
        {"user": m.user, "message": m.message, "timestamp": m.timestamp.isoformat()}
        for m in mensajes
    ]
    return JsonResponse(data, safe=False)
