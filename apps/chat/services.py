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
        user_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=content,
        )
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            status=Message.Status.GENERATING,
            in_reply_to=user_message,
        )
        transaction.on_commit(lambda: generate_answer.delay(str(assistant_message.id)))
    return conversation, assistant_message


def regenerate_answer(*, user, assistant_message_id):
    original = Message.objects.select_related("conversation", "in_reply_to").get(
        pk=assistant_message_id
    )
    conversation = original.conversation
    if original.role != Message.Role.ASSISTANT or conversation.created_by_id != user.id:
        raise PermissionError("没有重新生成该回答的权限")
    if original.status == Message.Status.GENERATING:
        raise ValueError("该回答仍在生成中")
    question = original.in_reply_to
    if question is None:
        question = (
            conversation.messages.filter(
                role=Message.Role.USER, created_at__lte=original.created_at
            )
            .order_by("-created_at")
            .first()
        )
    if question is None:
        raise ValueError("找不到该回答对应的问题")
    with transaction.atomic():
        regenerated = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            status=Message.Status.GENERATING,
            in_reply_to=question,
        )
        conversation.save(update_fields=["updated_at"])
        transaction.on_commit(lambda: generate_answer.delay(str(regenerated.id)))
    return conversation, regenerated
