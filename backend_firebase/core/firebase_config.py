import firebase_admin
from firebase_admin import credentials, firestore

# Carga la clave
cred = credentials.Certificate("firebase_key.json")

# Inicializa la app si aún no está inicializada
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Cliente Firestore
db = firestore.client()
