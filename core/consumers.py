from channels.generic.websocket import AsyncWebsocketConsumer
import json
from firebase_admin import auth as fb_auth
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Aceptar siempre la conexión entrante
        await self.accept()
        # Estado de autenticación
        self.authenticated = False

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.error("Payload no es JSON: %r", text_data)
            return await self.close(code=4003)

        # Fase de autenticación
        if not self.authenticated:
            # El primer mensaje debe ser de tipo 'auth' con token
            if data.get("type") != "auth" or "token" not in data:
                return await self.close(code=4001)

            # Verificar el ID token de Firebase
            try:
                decoded = fb_auth.verify_id_token(data["token"])
            except Exception as e:
                logger.warning("Auth fallida: %s", e)
                return await self.close(code=4002)

            # Autenticación exitosa
            self.authenticated = True
            self.user_id = decoded["uid"]
            self.username = decoded.get("name") or decoded.get("email") or self.user_id
            self.room = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group = f"chat_{self.room}"

            # Únete al grupo de la sala
            await self.channel_layer.group_add(self.room_group, self.channel_name)

            # Enviar ACK de autenticación
            await self.send_json({"type": "auth.success", "message": "Authenticated"})

            # Enviar historial (hasta 50 últimos mensajes)
            try:
                from core.models import ChatMessage

                def fetch_history():
                    qs = (
                        ChatMessage.objects.filter(room=self.room)
                        .order_by("id")
                        .values("user", "message")[:50]
                    )
                    return list(qs)

                history = await database_sync_to_async(fetch_history)()
                for msg in history:
                    await self.send_json(
                        {
                            "type": "history",
                            "user": msg["user"],
                            "message": msg["message"],
                        }
                    )
            except Exception as e:
                logger.error("Error al recuperar historial: %s", e)

            return

        # Fase de chat en vivo
        try:
            from core.models import ChatMessage

            # Guarda el mensaje en la base de datos
            msg_obj = await database_sync_to_async(ChatMessage.objects.create)(
                room=self.room, user=self.username, message=data.get("message", "")
            )
            # Reenvía al grupo
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "chat_message",
                    "user": msg_obj.user,
                    "message": msg_obj.message,
                },
            )
        except Exception as e:
            logger.error("Error al procesar mensaje en vivo: %s", e)
            return await self.close(code=1011)

    async def chat_message(self, event):
        # Enviar evento de mensaje al cliente
        await self.send_json(
            {
                "type": "chat.message",
                "user": event["user"],
                "message": event["message"],
            }
        )

    async def disconnect(self, code):
        # Al desconectar, abandonas el grupo
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
