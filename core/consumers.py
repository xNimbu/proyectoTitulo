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

        # Fase de autenticación inicial
        if not self.authenticated:
            # Validación de auth
            token = data.get("token")
            if not token:
                await self.close()
                return
            try:
                decoded = await database_sync_to_async(fb_auth.verify_id_token)(token)
            except Exception:
                await self.close()
                return

            self.authenticated = True
            self.user_id = decoded["uid"]
            self.username = decoded.get("name") or decoded.get("email") or self.user_id
            self.room = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group = f"chat_{self.room}"

            # Súmate al grupo
            await self.channel_layer.group_add(self.room_group, self.channel_name)

            # —— NUEVO: envía aquí el historial ——
            from core.models import ChatMessage

            last_messages = await database_sync_to_async(
                lambda: list(
                    ChatMessage.objects.filter(room=self.room)
                    .order_by("id")  # o por timestamp si lo tienes
                    .values("user", "message")[:50]
                )
            )()
            for m in last_messages:
                await self.send(
                    text_data=json.dumps(
                        {
                            "user": m["user"],
                            "message": m["message"],
                        }
                    )
                )
                return

    async def chat_message(self, event):
        # reenviar evento al cliente
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "user": event["user"],
                }
            )
        )

    async def disconnect(self, code):
        # al desconectar, sal del grupo
        await self.channel_layer.group_discard(self.room_group, self.channel_name)
