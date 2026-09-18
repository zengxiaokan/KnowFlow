import uuid

from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.identity.models import Organization


class KnowledgeBase(models.Model):
    class AccessScope(models.TextChoices):
        ORGANIZATION = "organization", "组织内可见"
        RESTRICTED = "restricted", "仅获授权成员"

    organization = models.ForeignKey(
        Organization, related_name="knowledge_bases", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    access_scope = models.CharField(
        max_length=16,
        choices=AccessScope.choices,
        default=AccessScope.ORGANIZATION,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="created_knowledge_bases", on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_knowledge_base_name_per_org"
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class KnowledgeBaseMembership(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        READER = "reader", "Reader"

    knowledge_base = models.ForeignKey(
        KnowledgeBase, related_name="memberships", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="knowledge_base_memberships",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.READER)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["knowledge_base", "user"], name="uniq_knowledge_base_member"
            )
        ]


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    knowledge_base = models.ForeignKey(
        KnowledgeBase, related_name="documents", on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)
    source_file = models.FileField(upload_to="documents/%Y/%m/%d")
    file_type = models.CharField(max_length=16)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    current_version = models.ForeignKey(
        "DocumentVersion",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="uploaded_documents", on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["knowledge_base", "status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, related_name="versions", on_delete=models.CASCADE)
    number = models.PositiveIntegerField(default=1)
    extracted_characters = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document", "number"], name="uniq_document_version_number"
            )
        ]
        ordering = ["-number"]


class IngestionTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        RETRYING = "retrying", "Retrying"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    class Stage(models.TextChoices):
        QUEUED = "queued", "Queued"
        EXTRACTING = "extracting", "Extracting"
        CHUNKING = "chunking", "Chunking"
        EMBEDDING = "embedding", "Embedding"
        INDEXING = "indexing", "Indexing"
        COMPLETE = "complete", "Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.ForeignKey(
        DocumentVersion, related_name="ingestion_tasks", on_delete=models.CASCADE
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Chunk(models.Model):
    knowledge_base = models.ForeignKey(
        KnowledgeBase, related_name="chunks", on_delete=models.CASCADE
    )
    document_version = models.ForeignKey(
        DocumentVersion, related_name="chunks", on_delete=models.CASCADE
    )
    ordinal = models.PositiveIntegerField()
    heading = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    page_start = models.PositiveSmallIntegerField(null=True, blank=True)
    page_end = models.PositiveSmallIntegerField(null=True, blank=True)
    embedding = VectorField(dimensions=settings.VECTOR_DIMENSIONS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["document_version", "ordinal"], name="uniq_document_chunk_ordinal"
            )
        ]
        indexes = [
            models.Index(fields=["knowledge_base", "document_version"]),
            HnswIndex(
                name="chunk_embedding_hnsw_cosine",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]
        ordering = ["ordinal"]
