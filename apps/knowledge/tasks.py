from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .chunking import split_into_chunks
from .events import publish_task
from .exceptions import DocumentParsingError, RetryableProviderError
from .models import Chunk, Document, IngestionTask
from .parsers import extract_text
from .providers import get_embedding_provider

EMBEDDING_BATCH_SIZE = 24


def embedding_text(document, payload) -> str:
    """Keep the document and section identity searchable alongside the body text."""
    heading = payload.heading or "正文"
    return f"文档标题：{document.title}\n章节：{heading}\n正文：{payload.content}"


def _set_task(task, *, status=None, stage=None, progress=None, **values):
    for key, value in values.items():
        setattr(task, key, value)
    if status is not None:
        task.status = status
    if stage is not None:
        task.stage = stage
    if progress is not None:
        task.progress = progress
    task.save()
    publish_task(task)


@shared_task(bind=True, max_retries=3)
def process_document(self, ingestion_task_id: str):
    task = IngestionTask.objects.select_related("document_version__document__knowledge_base").get(
        pk=ingestion_task_id
    )
    version = task.document_version
    document = version.document

    if task.status == IngestionTask.Status.SUCCEEDED:
        return {"task_id": str(task.id), "status": task.status}

    now = timezone.now()
    _set_task(
        task,
        status=IngestionTask.Status.PROCESSING,
        stage=IngestionTask.Stage.EXTRACTING,
        progress=5,
        celery_task_id=self.request.id or task.celery_task_id,
        attempt_count=self.request.retries + 1,
        started_at=task.started_at or now,
        error_code="",
        error_message="",
    )
    Document.objects.filter(pk=document.pk).update(status=Document.Status.PROCESSING)

    try:
        text, metadata = extract_text(document.source_file, document.file_type)
        version.extracted_characters = len(text)
        version.metadata = metadata
        version.save(update_fields=["extracted_characters", "metadata"])
        _set_task(task, stage=IngestionTask.Stage.CHUNKING, progress=30)

        payloads = split_into_chunks(text)
        if not payloads:
            raise DocumentParsingError("文档没有可用于检索的文本块")
        _set_task(task, stage=IngestionTask.Stage.EMBEDDING, progress=45)

        provider = get_embedding_provider()
        vectors: list[list[float]] = []
        for start in range(0, len(payloads), EMBEDDING_BATCH_SIZE):
            batch = payloads[start : start + EMBEDDING_BATCH_SIZE]
            vectors.extend(provider.embed([embedding_text(document, payload) for payload in batch]))
            from apps.chat.models import ModelUsageRecord

            ModelUsageRecord.objects.create(
                organization=document.knowledge_base.organization,
                user=document.created_by,
                provider=provider.provider_name,
                model=provider.model_name,
                kind=ModelUsageRecord.Kind.EMBEDDING,
                input_tokens=max(1, sum(len(item.content) for item in batch) // 4),
                output_tokens=0,
                is_estimated=True,
            )
            completed = min(start + len(batch), len(payloads))
            _set_task(
                task,
                progress=45 + int(completed / len(payloads) * 40),
            )

        _set_task(task, stage=IngestionTask.Stage.INDEXING, progress=90)
        with transaction.atomic():
            Chunk.objects.filter(document_version=version).delete()
            Chunk.objects.bulk_create(
                [
                    Chunk(
                        knowledge_base=document.knowledge_base,
                        document_version=version,
                        ordinal=payload.ordinal,
                        heading=payload.heading,
                        content=payload.content,
                        embedding=vector,
                    )
                    for payload, vector in zip(payloads, vectors, strict=True)
                ],
                batch_size=500,
            )
            document.current_version = version
            document.status = Document.Status.READY
            document.save(update_fields=["current_version", "status", "updated_at"])

        _set_task(
            task,
            status=IngestionTask.Status.SUCCEEDED,
            stage=IngestionTask.Stage.COMPLETE,
            progress=100,
            finished_at=timezone.now(),
        )
        return {"task_id": str(task.id), "chunks": len(payloads), "status": task.status}

    except RetryableProviderError as exc:
        if self.request.retries < self.max_retries:
            delay = 10 * (2**self.request.retries)
            _set_task(
                task,
                status=IngestionTask.Status.RETRYING,
                progress=task.progress,
                error_code="provider_unavailable",
                error_message=f"模型服务暂不可用，{delay} 秒后自动重试：{exc}",
            )
            raise self.retry(exc=exc, countdown=delay) from exc
        _fail_task(task, document, "provider_unavailable", str(exc))
        raise
    except DocumentParsingError as exc:
        _fail_task(task, document, exc.code, str(exc))
        return {"task_id": str(task.id), "status": task.status}
    except Exception as exc:
        _fail_task(task, document, "unexpected_error", str(exc))
        raise


def _fail_task(task, document, error_code: str, error_message: str):
    Document.objects.filter(pk=document.pk).update(status=Document.Status.FAILED)
    _set_task(
        task,
        status=IngestionTask.Status.FAILED,
        progress=task.progress,
        error_code=error_code,
        error_message=error_message[:2000],
        finished_at=timezone.now(),
    )


def enqueue_ingestion(task: IngestionTask) -> IngestionTask:
    Document.objects.filter(pk=task.document_version.document_id).update(
        status=Document.Status.UPLOADED
    )
    task.status = IngestionTask.Status.PENDING
    task.stage = IngestionTask.Stage.QUEUED
    task.progress = 0
    task.error_code = ""
    task.error_message = ""
    task.finished_at = None
    task.save(
        update_fields=[
            "status",
            "stage",
            "progress",
            "error_code",
            "error_message",
            "finished_at",
        ]
    )
    result = process_document.delay(str(task.id))
    task.celery_task_id = result.id
    task.save(update_fields=["celery_task_id"])
    publish_task(task)
    return task
