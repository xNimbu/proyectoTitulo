import firebase_admin
from firebase_admin import auth, credentials
from django.http import JsonResponse
from functools import wraps

# Asegúrate de que firebase_admin ya está inicializado desde firebase_config.py

def firebase_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        id_token = request.META.get('HTTP_AUTHORIZATION')

        if not id_token:
            return JsonResponse({'error': 'Token no proporcionado'}, status=401)

        try:
            # El token se espera como: "Bearer <token>"
            id_token = id_token.split(' ')[1]
            decoded_token = auth.verify_id_token(id_token)
            request.user_firebase = decoded_token
        except Exception as e:
            return JsonResponse({'error': f'Token inválido: {str(e)}'}, status=401)

        return view_func(request, *args, **kwargs)

    return _wrapped_view

def create_user(email, password, display_name=None):
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name if display_name else None
        )
        return {
            'uid': user.uid,
            'email': user.email,
            'display_name': user.display_name
        }
    except Exception as e:
        return {'error': str(e)}