from django.shortcuts import render
from django.http import JsonResponse
from .firebase_config import db

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