from django.shortcuts import render
from django.http import JsonResponse
from .firebase_config import db
from .auth import firebase_login_required

# Create your views here.
def hello_world(request):
    # Guardar algo en Firebase como prueba
    data = {
        'nombre': 'Alex Caldas',
        'email': 'alex@email.com',
        'proyecto': 'backend con Firebase'
    }

    # Guarda bajo colección 'usuarios' y documento con ID 'luis123'
    db.collection('usuarios').document('alex123').set(data)

    return JsonResponse({"mensaje": "Dato guardado en Firestore!"})

# Vista protegida por login Firebase
@firebase_login_required
def vista_protegida(request):
    usuario = request.user_firebase  # Datos del token verificado
    return JsonResponse({
        'mensaje': f'Hola {usuario["email"]}, tienes acceso!',
        'uid': usuario['uid']
    })

# NUEVA Vista para crear usuario en Firebase Auth
@csrf_exempt
def crear_usuario(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data['email']
            password = data['password']
            nombre = data.get('nombre', '')

            user = auth.create_user(
                email=email,
                password=password,
                display_name=nombre
            )

            return JsonResponse({'mensaje': 'Usuario creado', 'uid': user.uid}, status=201)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)