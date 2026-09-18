from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def task_group_name(task_id) -> str:
    return f"task.{task_id}"


def conversation_group_name(conversation_id) -> str:
    return f"conversation.{conversation_id}"


def publish_task(task) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = {
        "id": str(task.id),
        "status": task.status,
        "stage": task.stage,
        "progress": task.progress,
        "attempt_count": task.attempt_count,
        "error_code": task.error_code,
        "error_message": task.error_message,
    }
    async_to_sync(channel_layer.group_send)(
        task_group_name(task.id), {"type": "task.update", "payload": payload}
    )


def publish_conversation(conversation_id, event: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        conversation_group_name(conversation_id),
        {"type": "conversation.update", "event": event, "payload": payload},
    )
