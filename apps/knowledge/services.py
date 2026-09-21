import hashlib
from pathlib import Path

from django.db import transaction
from django.db.models import Max

from apps.identity.services import record_audit

from .forms import DocumentUploadForm
from .models import Document, DocumentVersion, IngestionTask
from .parsers import file_type_for
from .tasks import enqueue_ingestion


def sha256_for_upload(uploaded_file) -> str:
    digest = hashlib.sha256()
    for block in uploaded_file.chunks():
        digest.update(block)
    uploaded_file.seek(0)
    return digest.hexdigest()


def create_uploaded_document(*, user, knowledge_base, uploaded_file):
    form = DocumentUploadForm(files={"file": uploaded_file})
    if not form.is_valid():
        raise ValueError(form.errors["file"][0])
    uploaded_file = form.cleaned_data["file"]
    file_type = file_type_for(uploaded_file.name)
    digest = sha256_for_upload(uploaded_file)
    title = Path(uploaded_file.name).stem[:255]
    with transaction.atomic():
        document = Document.objects.create(
            knowledge_base=knowledge_base,
            title=title,
            source_file=uploaded_file,
            file_type=file_type,
            sha256=digest,
            created_by=user,
        )
        version = DocumentVersion.objects.create(
            document=document,
            number=1,
            source_file=document.source_file.name,
            file_type=file_type,
            sha256=digest,
        )
        ingestion_task = IngestionTask.objects.create(document_version=version)
        record_audit(
            organization=knowledge_base.organization,
            actor=user,
            event="document.uploaded",
            target=document,
            metadata={"file_type": file_type, "sha256": digest},
        )
        transaction.on_commit(lambda: enqueue_ingestion(ingestion_task))
    return document, ingestion_task


def create_document_version(*, user, document: Document, uploaded_file):
    form = DocumentUploadForm(files={"file": uploaded_file})
    if not form.is_valid():
        raise ValueError(form.errors["file"][0])
    uploaded_file = form.cleaned_data["file"]
    file_type = file_type_for(uploaded_file.name)
    digest = sha256_for_upload(uploaded_file)
    with transaction.atomic():
        next_number = (document.versions.aggregate(max_number=Max("number"))["max_number"] or 0) + 1
        document.source_file = uploaded_file
        document.file_type = file_type
        document.sha256 = digest
        document.status = Document.Status.UPLOADED
        document.save(update_fields=["source_file", "file_type", "sha256", "status", "updated_at"])
        version = DocumentVersion.objects.create(
            document=document,
            number=next_number,
            source_file=document.source_file.name,
            file_type=file_type,
            sha256=digest,
        )
        ingestion_task = IngestionTask.objects.create(document_version=version)
        record_audit(
            organization=document.knowledge_base.organization,
            actor=user,
            event="document.version_uploaded",
            target=document,
            metadata={
                "version": version.number,
                "file_type": file_type,
                "sha256": digest,
            },
        )
        transaction.on_commit(lambda: enqueue_ingestion(ingestion_task))
    return version, ingestion_task


def delete_document(*, user, document: Document):
    file_names = {
        name
        for name in [
            document.source_file.name,
            *document.versions.values_list("source_file", flat=True),
        ]
        if name
    }
    storage = document.source_file.storage
    with transaction.atomic():
        record_audit(
            organization=document.knowledge_base.organization,
            actor=user,
            event="document.deleted",
            target=document,
            metadata={"versions": document.versions.count()},
        )
        document.delete()
        transaction.on_commit(lambda: [storage.delete(name) for name in file_names])


def delete_knowledge_base(*, user, knowledge_base):
    file_names = set()
    storage = None
    for document in knowledge_base.documents.prefetch_related("versions"):
        storage = storage or document.source_file.storage
        if document.source_file.name:
            file_names.add(document.source_file.name)
        file_names.update(
            name for name in document.versions.values_list("source_file", flat=True) if name
        )
    with transaction.atomic():
        record_audit(
            organization=knowledge_base.organization,
            actor=user,
            event="knowledge_base.deleted",
            target=knowledge_base,
            metadata={"documents": knowledge_base.documents.count()},
        )
        knowledge_base.delete()
        if storage:
            transaction.on_commit(lambda: [storage.delete(name) for name in file_names])


def retry_ingestion(task: IngestionTask) -> IngestionTask:
    if task.status not in {IngestionTask.Status.FAILED, IngestionTask.Status.SUCCEEDED}:
        raise ValueError("只有已失败或已完成的任务可以重新处理")
    return enqueue_ingestion(task)
