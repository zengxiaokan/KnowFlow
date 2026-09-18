import uuid

import django.db.models.deletion
import pgvector.django
from django.conf import settings
from django.db import migrations, models


def create_vector_extension(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS vector")


def drop_vector_extension(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP EXTENSION IF EXISTS vector")


def create_hnsw_index(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "CREATE INDEX IF NOT EXISTS chunk_embedding_hnsw_cosine "
            "ON knowledge_chunk USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )


def drop_hnsw_index(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP INDEX IF EXISTS chunk_embedding_hnsw_cosine")


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_vector_extension, drop_vector_extension),
        migrations.CreateModel(
            name="KnowledgeBase",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_knowledge_bases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_bases",
                        to="identity.organization",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="KnowledgeBaseMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("manager", "Manager"), ("reader", "Reader")],
                        default="reader",
                        max_length=16,
                    ),
                ),
                (
                    "knowledge_base",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="knowledge.knowledgebase",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="knowledge_base_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("source_file", models.FileField(upload_to="documents/%Y/%m/%d")),
                ("file_type", models.CharField(max_length=16)),
                ("sha256", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("processing", "Processing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="uploaded",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="uploaded_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "knowledge_base",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="knowledge.knowledgebase",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["knowledge_base", "status"], name="knowledge_d_knowled_523ebd_idx"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="DocumentVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("number", models.PositiveIntegerField(default=1)),
                ("extracted_characters", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="knowledge.document",
                    ),
                ),
            ],
            options={"ordering": ["-number"]},
        ),
        migrations.AddField(
            model_name="document",
            name="current_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="knowledge.documentversion",
            ),
        ),
        migrations.CreateModel(
            name="IngestionTask",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("retrying", "Retrying"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("extracting", "Extracting"),
                            ("chunking", "Chunking"),
                            ("embedding", "Embedding"),
                            ("indexing", "Indexing"),
                            ("complete", "Complete"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("error_code", models.CharField(blank=True, max_length=64)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "document_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingestion_tasks",
                        to="knowledge.documentversion",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Chunk",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("ordinal", models.PositiveIntegerField()),
                ("heading", models.CharField(blank=True, max_length=255)),
                ("content", models.TextField()),
                ("page_start", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("page_end", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("embedding", pgvector.django.VectorField(dimensions=1024)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="knowledge.documentversion",
                    ),
                ),
                (
                    "knowledge_base",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="knowledge.knowledgebase",
                    ),
                ),
            ],
            options={
                "ordering": ["ordinal"],
                "indexes": [
                    models.Index(
                        fields=["knowledge_base", "document_version"],
                        name="knowledge_c_knowled_c91b0b_idx",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="knowledgebase",
            constraint=models.UniqueConstraint(
                fields=("organization", "name"), name="uniq_knowledge_base_name_per_org"
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgebasemembership",
            constraint=models.UniqueConstraint(
                fields=("knowledge_base", "user"), name="uniq_knowledge_base_member"
            ),
        ),
        migrations.AddConstraint(
            model_name="documentversion",
            constraint=models.UniqueConstraint(
                fields=("document", "number"), name="uniq_document_version_number"
            ),
        ),
        migrations.AddConstraint(
            model_name="chunk",
            constraint=models.UniqueConstraint(
                fields=("document_version", "ordinal"), name="uniq_document_chunk_ordinal"
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(create_hnsw_index, drop_hnsw_index)],
            state_operations=[
                migrations.AddIndex(
                    model_name="chunk",
                    index=pgvector.django.HnswIndex(
                        ef_construction=64,
                        fields=["embedding"],
                        m=16,
                        name="chunk_embedding_hnsw_cosine",
                        opclasses=["vector_cosine_ops"],
                    ),
                )
            ],
        ),
    ]
