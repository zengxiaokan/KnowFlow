from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.knowledge.events import conversation_group_name

from .markdown import render_assistant_markdown
from .models import Conversation, Message


@database_sync_to_async
def can_view_conversation(user, conversation_id) -> bool:
    if not user.is_authenticated:
        return False
    return Conversation.objects.filter(
        pk=conversation_id, organization__memberships__user=user, created_by=user
    ).exists()


@database_sync_to_async
def latest_answer_event(conversation_id):
    message = (
        Message.objects.filter(conversation_id=conversation_id, role=Message.Role.ASSISTANT)
        .prefetch_related("sources__document_version__document")
        .order_by("-created_at")
        .first()
    )
    if message is None:
        return None
    if message.status == Message.Status.GENERATING:
        return {"event": "answer.started", "message_id": str(message.id), "source_count": 0}
    if message.status == Message.Status.FAILED:
        return {
            "event": "answer.failed",
            "message_id": str(message.id),
            "error": message.error_message,
        }
    return {
        "event": "answer.completed",
        "message_id": str(message.id),
        "content": message.content,
        "rendered_content": render_assistant_markdown(message.content),
        "sources": [
            {
                "id": source.id,
                "title": source.document_version.document.title,
                "heading": source.heading,
                "ordinal": source.ordinal,
            }
            for source in message.sources.all()
        ],
    }


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        if not await can_view_conversation(self.scope["user"], self.conversation_id):
            await self.close(code=4403)
            return
        self.group_name = conversation_group_name(self.conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        recovery_event = await latest_answer_event(self.conversation_id)
        if recovery_event:
            await self.send_json(recovery_event)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def conversation_update(self, event):
        await self.send_json({"event": event["event"], **event["payload"]})
