from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .firebase_config import db
from .auth import firebase_login_required
from firebase_admin import auth as firebase_auth

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
    GET  /api/profile/        → devuelve perfil + lista de mascotas
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

        # Traer mascotas
        pets = []
        for pet_snap in doc_ref.collection("pets").stream():
            p = pet_snap.to_dict()
            p["id"] = pet_snap.id
            pets.append(p)
        profile_data["pets"] = pets

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
