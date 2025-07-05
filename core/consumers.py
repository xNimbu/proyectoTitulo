# core/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
from urllib.parse import parse_qs
import json
from firebase_admin import auth as fb_auth
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1) Leer token JWT de la query string
        query = parse_qs(self.scope["query_string"].decode())
        token = query.get("token", [None])[0]
        if not token:
            logger.warning("No se recibió token en URL")
            return await self.close(code=4001)

        # 2) Verificar token con Firebase
        try:
            decoded = fb_auth.verify_id_token(token)
        except Exception as e:
            logger.warning("Token inválido: %s", e)
            return await self.close(code=4002)

        # 3) Autenticación OK → configurar usuario y sala
        self.user_id = decoded["uid"]
        self.username = decoded.get("name") or decoded.get("email") or self.user_id
        self.room = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group = f"chat_{self.room}"

        # 4) Unirse al grupo y aceptar la conexión
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # 5) Enviar historial (hasta 50 mensajes)
        try:
            from core.models import ChatMessage

            def fetch_history_and_mark():
                mensajes = ChatMessage.objects.filter(room=self.room).order_by("id")[:50]
                datos = []
                for m in mensajes:
                    if self.user_id not in m.read_by:
                        m.read_by.append(self.user_id)
                        m.save(update_fields=["read_by"])
                    datos.append({"user": m.user, "message": m.message})
                return datos

            history = await database_sync_to_async(fetch_history_and_mark)()
            for msg in history:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "history",
                            "user": msg["user"],
                            "message": msg["message"],
                        }
                    )
                )
        except Exception as e:
            logger.error("Error cargando historial: %s", e)

    async def receive(self, text_data):
        # TODO: Validar JSON…
        data = json.loads(text_data)
        # Guardar y reenviar
        from core.models import ChatMessage

        msg_obj = await database_sync_to_async(ChatMessage.objects.create)(
            room=self.room,
            user=self.username,
            message=data.get("message", ""),
            read_by=[self.user_id],
        )
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "chat.message",
                "user": msg_obj.user,
                "message": msg_obj.message,
            },
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.message",
                    "user": event["user"],
                    "message": event["message"],
                }
            )
        )

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)
