import uuid

from django.conf import settings
from django.db import models

from apps.identity.models import Organization
from apps.knowledge.models import Chunk, KnowledgeBase


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, related_name="conversations", on_delete=models.CASCADE
    )
    knowledge_base = models.ForeignKey(
        KnowledgeBase, related_name="conversations", on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="conversations", on_delete=models.PROTECT
    )
    title = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    class Status(models.TextChoices):
        COMPLETE = "complete", "Complete"
        GENERATING = "generating", "Generating"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETE)
    sources = models.ManyToManyField(Chunk, related_name="citing_messages", blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ModelUsageRecord(models.Model):
    class Kind(models.TextChoices):
        EMBEDDING = "embedding", "Embedding"
        CHAT = "chat", "Chat"
        WORKFLOW = "workflow", "Workflow"

    organization = models.ForeignKey(
        Organization, related_name="model_usage", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="model_usage", on_delete=models.PROTECT
    )
    conversation = models.ForeignKey(
        Conversation, related_name="usage_records", null=True, blank=True, on_delete=models.SET_NULL
    )
    provider = models.CharField(max_length=64)
    model = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    is_estimated = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(default=0)
    succeeded = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "created_at"])]
        ordering = ["-created_at"]
