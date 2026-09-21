from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.knowledge.models import Chunk, Document, DocumentVersion, KnowledgeBase
from apps.knowledge.providers import ChatDelta

from ..models import Conversation, Message
from ..tasks import generate_answer


class FakeChatProvider:
    provider_name = "fake"
    model_name = "fake-chat"

    def stream(self, messages):
        yield ChatDelta(text="这是 **加粗重点**。\n\n- 第一项\n- 第二项")


class RecordingChatProvider:
    provider_name = "fake"
    model_name = "fake-chat"

    def __init__(self):
        self.messages = []

    def stream(self, messages):
        self.messages = messages
        yield ChatDelta(text="根据上一轮内容继续回答。")


@pytest.mark.django_db
@patch("apps.chat.tasks.publish_conversation")
@patch("apps.chat.tasks.get_chat_provider", return_value=FakeChatProvider())
@patch("apps.chat.tasks._retrieve_sources")
def test_generate_answer_publishes_sanitised_markdown(
    retrieve_sources, get_chat_provider, publish_conversation
):
    user = User.objects.create_user(username="writer", password="test-pass-123")
    organization = user.organization_memberships.get().organization
    knowledge_base = KnowledgeBase.objects.create(
        organization=organization, name="资料", created_by=user
    )
    document = Document.objects.create(
        knowledge_base=knowledge_base,
        title="来源",
        source_file=SimpleUploadedFile("source.md", b"source"),
        file_type="md",
        sha256="0" * 64,
        created_by=user,
        status=Document.Status.READY,
    )
    version = DocumentVersion.objects.create(document=document)
    document.current_version = version
    document.save(update_fields=["current_version"])
    chunk = Chunk.objects.create(
        knowledge_base=knowledge_base,
        document_version=version,
        ordinal=1,
        content="资料正文",
        embedding=[0.0] * 1024,
    )
    conversation = Conversation.objects.create(
        organization=organization,
        knowledge_base=knowledge_base,
        created_by=user,
    )
    Message.objects.create(conversation=conversation, role=Message.Role.USER, content="问题")
    assistant = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        status=Message.Status.GENERATING,
    )
    retrieve_sources.return_value = [chunk]

    generate_answer.apply(args=(str(assistant.id),)).get()

    completed_payload = [
        call.args[2]
        for call in publish_conversation.call_args_list
        if call.args[1] == "answer.completed"
    ][0]
    assert "<strong>加粗重点</strong>" in completed_payload["rendered_content"]
    assert "<ul>" in completed_payload["rendered_content"]


@pytest.mark.django_db
@patch("apps.chat.tasks.publish_conversation")
@patch("apps.chat.tasks._retrieve_sources")
def test_generate_answer_uses_previous_conversation_turn_as_memory(
    retrieve_sources, publish_conversation
):
    user = User.objects.create_user(username="memory-writer", password="test-pass-123")
    organization = user.organization_memberships.get().organization
    knowledge_base = KnowledgeBase.objects.create(
        organization=organization, name="资料", created_by=user
    )
    document = Document.objects.create(
        knowledge_base=knowledge_base,
        title="Java基础面试篇",
        source_file=SimpleUploadedFile("source.md", b"source"),
        file_type="md",
        sha256="1" * 64,
        created_by=user,
        status=Document.Status.READY,
    )
    version = DocumentVersion.objects.create(document=document)
    document.current_version = version
    document.save(update_fields=["current_version"])
    chunk = Chunk.objects.create(
        knowledge_base=knowledge_base,
        document_version=version,
        ordinal=1,
        content="Java 支持平台无关性和面向对象。",
        embedding=[0.0] * 1024,
    )
    conversation = Conversation.objects.create(
        organization=organization,
        knowledge_base=knowledge_base,
        created_by=user,
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content="随机给我出三道 Java 基础面试题",
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content="第一题是 JVM 与字节码的关系。",
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content="好的给我答案",
    )
    assistant = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        status=Message.Status.GENERATING,
    )
    provider = RecordingChatProvider()
    retrieve_sources.return_value = [chunk]

    with patch("apps.chat.tasks.get_chat_provider", return_value=provider):
        generate_answer.apply(args=(str(assistant.id),)).get()

    assert any(
        "随机给我出三道 Java 基础面试题" in message["content"] for message in provider.messages
    )


@pytest.mark.django_db
@patch("apps.chat.tasks.publish_conversation")
@patch("apps.chat.tasks.get_chat_provider")
@patch("apps.chat.tasks._retrieve_sources", return_value=[])
def test_generate_answer_returns_a_clear_message_when_no_source_is_relevant(
    retrieve_sources, get_chat_provider, publish_conversation
):
    user = User.objects.create_user(username="no-source", password="test-pass-123")
    organization = user.organization_memberships.get().organization
    knowledge_base = KnowledgeBase.objects.create(
        organization=organization, name="资料", created_by=user
    )
    conversation = Conversation.objects.create(
        organization=organization,
        knowledge_base=knowledge_base,
        created_by=user,
    )
    question = Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content="与资料无关的问题",
    )
    assistant = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        status=Message.Status.GENERATING,
        in_reply_to=question,
    )

    generate_answer.apply(args=(str(assistant.id),)).get()

    assistant.refresh_from_db()
    assert assistant.status == Message.Status.COMPLETE
    assert assistant.content.startswith("未找到与该问题相关的资料")
    get_chat_provider.assert_not_called()
