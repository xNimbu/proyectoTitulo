# core/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
import json
from firebase_admin import auth as fb_auth
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.authenticated = False

    async def receive(self, text_data):
        # 1) Parsear JSON
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.error("Payload no es JSON: %r", text_data)
            return await self.close(code=4003)

        # 2) Fase de autenticación
        if not self.authenticated:
            # Debe venir { type: 'auth', token: '...' }
            if data.get("type") != "auth" or "token" not in data:
                return await self.close(code=4001)

            # Verificar token con Firebase
            try:
                decoded = fb_auth.verify_id_token(data["token"])
            except Exception as e:
                logger.warning("Auth fallida: %s", e)
                return await self.close(code=4002)

            # Autenticación exitosa: guardamos usuario y sala
            self.authenticated = True
            self.user_id = decoded["uid"]
            self.username = decoded.get("name") or decoded.get("email") or self.user_id
            self.room = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group = f"chat_{self.room}"

            # Nos unimos al grupo
            await self.channel_layer.group_add(self.room_group, self.channel_name)

            # Enviamos ACK de autenticación
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "auth.success",
                        "message": "Authenticated",
                    }
                )
            )

            # Enviamos historial hasta 50 mensajes
            try:
                from core.models import ChatMessage

                def fetch_history():
                    return list(
                        ChatMessage.objects.filter(room=self.room)
                        .order_by("id")
                        .values("user", "message")[:50]
                    )

                history = await database_sync_to_async(fetch_history)()
                for msg in history:
                    await self.send(text_data=json.dumps(
                        {
                            "type": "history",
                            "user": msg["user"],
                            "message": msg["message"],
                        }
                    ))
            except Exception as e:
                logger.error("Error al recuperar historial: %s", e)

            # Terminamos aquí: no procesamos este mensaje como chat real
            return

        # 3) Fase de chat “en vivo”
        # Ya estamos autenticados…
        try:
            from core.models import ChatMessage

            # Guardar en BD
            msg_obj = await database_sync_to_async(ChatMessage.objects.create)(
                room=self.room, user=self.username, message=data.get("message", "")
            )

            # Reenviar al grupo
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "chat.message",
                    "user": msg_obj.user,
                    "message": msg_obj.message,
                },
            )
        except Exception as e:
            logger.error("Error al procesar mensaje en vivo: %s", e)
            return await self.close(code=1011)

    async def chat_message(self, event):
        # Handler para reenviar mensajes del grupo al cliente
        await self.send(text_data=json.dumps(
            {
                "type": "chat.message",
                "user": event["user"],
                "message": event["message"],
            }
        ))

    async def disconnect(self, code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
