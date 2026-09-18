import hashlib
from pathlib import Path

from django.db import transaction

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
        version = DocumentVersion.objects.create(document=document, number=1)
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


def retry_ingestion(task: IngestionTask) -> IngestionTask:
    if task.status not in {IngestionTask.Status.FAILED, IngestionTask.Status.SUCCEEDED}:
        raise ValueError("只有已失败或已完成的任务可以重新处理")
    return enqueue_ingestion(task)
