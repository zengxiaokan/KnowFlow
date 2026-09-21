from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from apps.chat.models import Message
from apps.chat.services import regenerate_answer, submit_question
from apps.knowledge.models import KnowledgeBase


@pytest.mark.django_db
@patch("apps.chat.services.generate_answer.delay")
def test_submit_question_creates_user_and_pending_assistant_messages(
    delay, django_capture_on_commit_callbacks
):
    user = User.objects.create_user(username="reader", password="test-pass-123")
    organization = user.organization_memberships.get().organization
    knowledge_base = KnowledgeBase.objects.create(
        organization=organization, name="资料", created_by=user
    )

    with django_capture_on_commit_callbacks(execute=True):
        conversation, assistant = submit_question(
            user=user, knowledge_base_id=knowledge_base.id, content="项目如何部署？"
        )

    assert assistant.status == Message.Status.GENERATING
    assert assistant.in_reply_to_id == conversation.messages.get(role=Message.Role.USER).id
    assert conversation.messages.count() == 2
    delay.assert_called_once_with(str(assistant.id))


@pytest.mark.django_db
@patch("apps.chat.services.generate_answer.delay")
def test_regeneration_reuses_the_original_question(delay, django_capture_on_commit_callbacks):
    user = User.objects.create_user(username="regenerator", password="test-pass-123")
    organization = user.organization_memberships.get().organization
    knowledge_base = KnowledgeBase.objects.create(
        organization=organization, name="资料", created_by=user
    )
    with django_capture_on_commit_callbacks(execute=True):
        conversation, original = submit_question(
            user=user, knowledge_base_id=knowledge_base.id, content="第一道题是什么？"
        )
    original.status = Message.Status.COMPLETE
    original.content = "第一道题是 JVM。"
    original.save(update_fields=["status", "content"])
    Message.objects.create(conversation=conversation, role=Message.Role.USER, content="另一个问题")

    with django_capture_on_commit_callbacks(execute=True):
        _, regenerated = regenerate_answer(user=user, assistant_message_id=original.id)

    assert regenerated.in_reply_to_id == original.in_reply_to_id
    assert regenerated.status == Message.Status.GENERATING
    assert delay.call_args_list[-1].args == (str(regenerated.id),)
