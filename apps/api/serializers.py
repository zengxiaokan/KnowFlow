from rest_framework import serializers

from apps.chat.models import Conversation, Message, ModelUsageRecord
from apps.knowledge.models import Document, IngestionTask, KnowledgeBase
from apps.workflows.models import Workflow, WorkflowRun


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBase
        fields = ["id", "name", "description", "access_scope", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    knowledge_base = serializers.PrimaryKeyRelatedField(queryset=KnowledgeBase.objects.all())

    class Meta:
        model = Document
        fields = [
            "id",
            "knowledge_base",
            "title",
            "source_file",
            "file_type",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "title", "file_type", "status", "created_at", "updated_at"]


class IngestionTaskSerializer(serializers.ModelSerializer):
    document_id = serializers.IntegerField(source="document_version.document_id", read_only=True)

    class Meta:
        model = IngestionTask
        fields = [
            "id",
            "document_id",
            "status",
            "stage",
            "progress",
            "attempt_count",
            "error_code",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        ]


class MessageSerializer(serializers.ModelSerializer):
    sources = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "role", "content", "status", "error_message", "sources", "created_at"]

    def get_sources(self, message):
        return [
            {
                "id": chunk.id,
                "title": chunk.document_version.document.title,
                "heading": chunk.heading,
                "ordinal": chunk.ordinal,
            }
            for chunk in message.sources.select_related("document_version__document").all()
        ]


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "knowledge_base", "title", "messages", "created_at", "updated_at"]
        read_only_fields = ["id", "title", "messages", "created_at", "updated_at"]


class ModelUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelUsageRecord
        fields = [
            "id",
            "provider",
            "model",
            "kind",
            "input_tokens",
            "output_tokens",
            "is_estimated",
            "latency_ms",
            "succeeded",
            "created_at",
        ]


class WorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = ["id", "name", "description", "knowledge_base", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class WorkflowRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRun
        fields = [
            "id",
            "workflow_version",
            "status",
            "input_data",
            "output_data",
            "error_message",
            "created_at",
        ]
