from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .firebase_config import db
from .auth import firebase_login_required
from firebase_admin import auth as firebase_auth
from google.cloud import firestore
from datetime import datetime
from core.models import ChatMessage
import requests
import os
from google.cloud import firestore

from core import auth


# Create your views here.
def hello_world(request):
    # Guardar algo en Firebase como prueba
    data = {
        "nombre": "Alex Caldas",
        "email": "alex@email.com",
        "proyecto": "backend con Firebase",
    }

    # Guarda bajo colección 'usuarios' y documento con ID 'luis123'
    db.collection("usuarios").document("alex123").set(data)

    return JsonResponse({"mensaje": "Dato guardado en Firestore!"})


# Vista protegida por login Firebase
@firebase_login_required
def vista_protegida(request):
    usuario = request.user_firebase  # Datos del token verificado
    return JsonResponse(
        {"mensaje": f'Hola {usuario["email"]}, tienes acceso!', "uid": usuario["uid"]}
    )


# NUEVA Vista para crear usuario en Firebase Auth
@csrf_exempt
def crear_usuario(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data["email"]
            password = data["password"]
            nombre = data.get("nombre", "")

            user = auth.create_user(email=email, password=password, display_name=nombre)

            return JsonResponse(
                {"mensaje": "Usuario creado", "uid": user.uid}, status=201
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Método no permitido"}, status=405)


# Obtener información del usuario autenticado
@csrf_exempt
@firebase_login_required
def profile(request):
    """
    GET  /api/profile/        → devuelve perfil + lista de mascotas + lista de posts
    POST /api/profile/        → crea/actualiza perfil
    """
    uid = request.user_firebase["uid"]
    email = request.user_firebase["email"]
    doc_ref = db.collection("profiles").document(uid)

    if request.method == "GET":
        snap = doc_ref.get()
        if not snap.exists:
            return JsonResponse({"error": "Perfil no encontrado"}, status=404)
        profile_data = snap.to_dict()

        # 1) Traer mascotas
        pets = []
        for pet_snap in doc_ref.collection("pets").stream():
            p = pet_snap.to_dict()
            p["id"] = pet_snap.id
            pets.append(p)
        profile_data["pets"] = pets

        # 2) Traer publicaciones (posts), ordenadas por timestamp descendente
        posts = []
        posts_ref = doc_ref.collection("posts")
        # para usar order_by necesitas importar:
        # from google.cloud import firestore
        for post_snap in posts_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream():
            post = post_snap.to_dict()
            post["id"] = post_snap.id
            posts.append(post)
        profile_data["posts"] = posts

        return JsonResponse(profile_data)

    elif request.method in ("POST", "PUT"):
        data = json.loads(request.body)
        # Construye el objeto que quieres guardar
        perfil = {
            "fullName": data.get("fullName"),
            "username": data.get("username"),
            "email": email,  # confías en Firebase para el email
            "phone": data.get("phone"),
            "role": data.get("role"),
            "photoURL": data.get("photoURL"),
        }
        # guardamos (merge = true para actualizar sin borrar campos extra)
        doc_ref.set(perfil, merge=True)
        return JsonResponse({"mensaje": "Perfil guardado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def pets(request):
    """
    GET  /api/profile/pets/           → lista todas las mascotas
    POST /api/profile/pets/           → crea una nueva mascota
    """
    uid = request.user_firebase["uid"]
    col_ref = db.collection("profiles").document(uid).collection("pets")

    if request.method == "GET":
        lista = []
        for pet_snap in col_ref.stream():
            pet = pet_snap.to_dict()
            pet["id"] = pet_snap.id
            lista.append(pet)
        return JsonResponse({"pets": lista})

    elif request.method == "POST":
        data = json.loads(request.body)
        nueva = {
            "name": data["name"],
            "breed": data.get("breed"),
            "age": data.get("age"),
            "type": data.get("type"),
            "photoURL": data.get("photoURL"),
        }
        _, doc_ref = col_ref.add(nueva)
        return JsonResponse({"mensaje": "Mascota creada", "id": doc_ref.id})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def pet_detail(request, pet_id):
    """
    PUT    /api/profile/pets/<pet_id>/ → actualiza una mascota
    DELETE /api/profile/pets/<pet_id>/ → elimina una mascota
    """
    uid = request.user_firebase["uid"]
    doc_ref = (
        db.collection("profiles").document(uid).collection("pets").document(pet_id)
    )

    if request.method == "PUT":
        data = json.loads(request.body)
        doc_ref.update(data)
        return JsonResponse({"mensaje": "Mascota actualizada"})

    elif request.method == "DELETE":
        doc_ref.delete()
        return JsonResponse({"mensaje": "Mascota eliminada"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
def profile_list(request):
    """
    GET /api/profile_list/  → devuelve un arreglo con todos los perfiles existentes
    (no requiere token si lo expones como público).
    """
    if request.method == "GET":
        perfiles = []
        # Recorremos todos los documentos bajo "profiles"
        for doc_snap in db.collection("profiles").stream():
            data = doc_snap.to_dict()
            # Agregamos el campo 'uid' (opcional) para identificar al documento
            data["uid"] = doc_snap.id

            # Aseguramos que existan los campos que Angular espera:
            #   - username (string)
            #   - avatar (string)   – en tu modelo lo llamas "photoURL"
            #   - unreadCount (número) – puede venir de tu lógica o inicializarse a 0
            perfil = {
                "username": data.get("username", ""),  # p.ej. "ilusm"
                "avatar": data.get(
                    "photoURL", ""
                ),  # si guardaste photoURL en Firestore
                "unreadCount": data.get(
                    "unreadCount", 0
                ),  # si no lo tienes, lo inicializas a 0
            }
            perfiles.append(perfil)

        return JsonResponse(perfiles, safe=False)

    return JsonResponse({"error": "Método no permitido"}, status=405)


def chat_history(request, room):
    """
    GET /api/chat/<room>/history/ → lista todos los mensajes de la sala ordenados por timestamp
    """
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    # Filtramos por room y devolvemos sólo user+message (puedes añadir timestamp si quieres)
    mensajes = ChatMessage.objects.filter(room=room)
    data = [
        {"user": m.user, "message": m.message, "timestamp": m.timestamp.isoformat()}
        for m in mensajes
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
@firebase_login_required
def user_posts(request):
    """
    GET  /api/profile/posts/        → Lista los posts del usuario autenticado
    POST /api/profile/posts/        → Crea un nuevo post con texto e imagen
    """
    uid = request.user_firebase["uid"]
    posts_ref = db.collection("profiles").document(uid).collection("posts")

    if request.method == "GET":
        lista = []
        for doc in posts_ref.order_by("timestamp", direction="DESCENDING").stream():
            post = doc.to_dict()
            post["id"] = doc.id
            lista.append(post)
        return JsonResponse({"posts": lista})

    elif request.method == "POST":
        content = request.POST.get("content", "")
        photoURL = ""
        image_file = request.FILES.get("image")

        if image_file:
            try:
                imgbb_api_key = os.getenv("IMGBB_API_KEY")
                upload = requests.post(
                    "https://api.imgbb.com/1/upload",
                    params={"key": imgbb_api_key},
                    files={"image": image_file.read()},
                )
                if upload.status_code == 200:
                    photoURL = upload.json()["data"]["url"]
            except Exception as e:
                return JsonResponse({"error": f"Error subiendo imagen: {str(e)}"}, status=400)

        nuevo = {
            "content": content,
            "photoURL": photoURL,
            "timestamp": datetime.utcnow(),
        }

        _, doc_ref = posts_ref.add(nuevo)
        return JsonResponse({"mensaje": "Post creado", "id": doc_ref.id})

    return JsonResponse({"error": "Método no permitido"}, status=405)



@csrf_exempt
@firebase_login_required
def user_post_detail(request, post_id):
    """
    PUT    /profile/posts/<post_id>/     → Actualiza un post
    DELETE /profile/posts/<post_id>/     → Elimina un post
    """
    uid = request.user_firebase["uid"]
    doc_ref = (
        db.collection("profiles").document(uid).collection("posts").document(post_id)
    )

    if request.method == "PUT":
        data = json.loads(request.body)

        # Obtener el post actual para conservar el photoURL si no se manda nuevo
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            return JsonResponse({"error": "Post no encontrado"}, status=404)
        post_actual = doc_snapshot.to_dict()

        nuevo_content = data.get("content", post_actual.get("content"))
        nuevo_photoURL = data.get("photoURL", post_actual.get("photoURL"))

        doc_ref.update({
            "content": nuevo_content,
            "photoURL": nuevo_photoURL,
            "timestamp": datetime.utcnow(),
        })
        return JsonResponse({"mensaje": "Post actualizado"})

    elif request.method == "DELETE":
        doc_ref.delete()
        return JsonResponse({"mensaje": "Post eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def comments(request, post_id):
    comments_ref = db.collection("posts").document(post_id).collection("comments")

    if request.method == "GET":
        lista = []
        for c in comments_ref.order_by("timestamp").stream():
            comment = c.to_dict()
            comment["id"] = c.id
            lista.append(comment)
        return JsonResponse({"comments": lista})

    elif request.method == "POST":
        user = request.user_firebase
        data = json.loads(request.body)
        nuevo = {
            "userId": user["uid"],
            "username": user["email"],
            "message": data.get("message"),
            "timestamp": datetime.utcnow(),
        }
        _, doc_ref = comments_ref.add(nuevo)
        return JsonResponse({"mensaje": "Comentario agregado", "id": doc_ref.id})

    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
@firebase_login_required
def comment_detail(request, post_id, comment_id):
    comment_ref = (
        db.collection("posts")
        .document(post_id)
        .collection("comments")
        .document(comment_id)
    )

    if request.method == "PUT":
        data = json.loads(request.body)
        comment_ref.update(
            {
                "message": data.get("message"),
                "timestamp": datetime.utcnow(),
            }
        )
        return JsonResponse({"mensaje": "Comentario actualizado"})

    elif request.method == "DELETE":
        comment_ref.delete()
        return JsonResponse({"mensaje": "Comentario eliminado"})

    return JsonResponse({"error": "Método no permitido"}, status=405)
