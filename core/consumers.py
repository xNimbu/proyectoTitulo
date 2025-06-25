# core/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
from urllib.parse import parse_qs
import json
import firebase_admin
from firebase_admin import auth as fb_auth
from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1) Extraer token de la query string
        qs = parse_qs(self.scope["query_string"].decode())
        token = qs.get("token", [None])[0]
        if not token:
            # Cierra con código 4001 si no viene token
            return await self.close(code=4001)

        # 2) Verificar el ID token de Firebase
        try:
            decoded = fb_auth.verify_id_token(token)
        except Exception:
            # Cierra con código 4002 si el token no es válido
            return await self.close(code=4002)

        # 3) Extraer datos de usuario
        self.user_id = decoded["uid"]
        self.username = decoded.get("name") or decoded.get("email") or self.user_id

        # 4) Lógica de sala
        # Usa 'room_name' porque así lo defines en routing.py
        self.room = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group = f"chat_{self.room}"

        # Agrégate al grupo de Channels
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        # Finalmente acepta la conexión
        await self.accept()

    async def disconnect(self, code):
        # Al desconectar, te quitas del grupo
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        # Importa el modelo aquí dentro para evitar AppRegistryNotReady
        from core.models import ChatMessage

        data = json.loads(text_data)
        # Guarda el mensaje en la base de datos
        msg = await database_sync_to_async(ChatMessage.objects.create)(
            room=self.room,
            user=data.get("user", self.username),
            message=data["message"],
        )
        # Envía el mensaje a todo el grupo
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "chat.message",
                "message": msg.message,
                "user": msg.user,
            },
        )

    async def chat_message(self, event):
        # Recibe un evento de tipo 'chat.message' y reenvíalo al cliente
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "user": event["user"],
                }
            )
        )
