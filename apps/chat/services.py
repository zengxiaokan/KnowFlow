from django.db import transaction

from apps.knowledge.permissions import get_visible_knowledge_base

from .models import Conversation, Message
from .tasks import generate_answer


def submit_question(*, user, knowledge_base_id, content: str, conversation_id=None):
    knowledge_base = get_visible_knowledge_base(user, knowledge_base_id)
    content = content.strip()
    if not content:
        raise ValueError("问题不能为空")
    with transaction.atomic():
        if conversation_id:
            conversation = Conversation.objects.get(
                pk=conversation_id,
                knowledge_base=knowledge_base,
                organization=knowledge_base.organization,
                created_by=user,
            )
        else:
            conversation = Conversation.objects.create(
                organization=knowledge_base.organization,
                knowledge_base=knowledge_base,
                created_by=user,
                title=content[:80],
            )
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=content,
        )
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            status=Message.Status.GENERATING,
        )
        transaction.on_commit(lambda: generate_answer.delay(str(assistant_message.id)))
    return conversation, assistant_message
