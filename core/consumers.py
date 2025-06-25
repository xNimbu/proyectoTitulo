# core/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
import json
from firebase_admin import auth as fb_auth
from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1) Acepta siempre
        await self.accept()
        # 2) Marca como no autenticado todavía
        self.authenticated = False

    async def receive(self, text_data):
        data = json.loads(text_data)

        # --- fase de autenticación inicial ---
        if not self.authenticated:
            # el primer mensaje debe tener tipo/auth y el token
            if data.get("type") != "auth" or "token" not in data:
                return await self.close(code=4001)
            # verifica token Firebase
            try:
                decoded = fb_auth.verify_id_token(data["token"])
            except Exception:
                return await self.close(code=4002)
            # éxito: guarda user y súmate al grupo
            self.authenticated = True
            self.user_id      = decoded["uid"]
            self.username     = decoded.get("name") or decoded.get("email") or self.user_id
            self.room         = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group   = f"chat_{self.room}"
            await self.channel_layer.group_add(self.room_group, self.channel_name)
            return  # no proceses este mensaje como chat

        # --- fase de mensajes normales ---
        from core.models import ChatMessage  # lazy import

        msg = await database_sync_to_async(ChatMessage.objects.create)(
            room=self.room,
            user=self.username,
            message=data.get("message", "")
        )
        await self.channel_layer.group_send(
            self.room_group,
            {"type": "chat.message", "message": msg.message, "user": msg.user},
        )

    async def chat_message(self, event):
        # reenviar evento al cliente
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "user":    event["user"],
        }))

    async def disconnect(self, code):
        # al desconectar, sal del grupo
        await self.channel_layer.group_discard(self.room_group, self.channel_name)
