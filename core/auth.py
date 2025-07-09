import firebase_admin
from firebase_admin import auth, credentials
from django.http import JsonResponse
from functools import wraps

# Asegúrate de que firebase_admin ya está inicializado desde firebase_config.py


def firebase_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        """Verifica el token de Firebase en encabezado, cookie o query string."""
        raw_auth = request.META.get("HTTP_AUTHORIZATION", "")
        token = ""

        if raw_auth.startswith("Bearer "):
            token = raw_auth.split(" ", 1)[1]

        if not token:
            token = request.COOKIES.get("token") or request.GET.get("token")

        if not token:
            return JsonResponse({"error": "Token no proporcionado"}, status=401)

        try:
            decoded_token = auth.verify_id_token(token)
            request.user_firebase = decoded_token
        except Exception as e:
            return JsonResponse({"error": f"Token inválido: {str(e)}"}, status=401)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def create_user(email: str, password: str, display_name: str = None) -> auth.UserRecord:
    """
    Crea un usuario en Firebase Auth y retorna el UserRecord.
    Lanza excepción si hay error.
    """
    return auth.create_user(
        email=email,
        password=password,
        display_name=display_name or None,
    )
