from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .events import task_group_name
from .models import IngestionTask
from .permissions import visible_knowledge_bases


@database_sync_to_async
def can_view_task(user, task_id) -> bool:
    if not user.is_authenticated:
        return False
    return IngestionTask.objects.filter(
        pk=task_id,
        document_version__document__knowledge_base__in=visible_knowledge_bases(user),
    ).exists()


class IngestionTaskConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope["url_route"]["kwargs"]["task_id"]
        if not await can_view_task(self.scope["user"], self.task_id):
            await self.close(code=4403)
            return
        self.group_name = task_group_name(self.task_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def task_update(self, event):
        await self.send_json(event["payload"])
