from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from apps.chat.models import Message
from apps.chat.services import submit_question
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
    assert conversation.messages.count() == 2
    delay.assert_called_once_with(str(assistant.id))
