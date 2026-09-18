from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.chat.models import Conversation, ModelUsageRecord
from apps.identity.models import Membership
from apps.identity.services import record_audit

from .forms import DocumentBatchUploadForm, KnowledgeBaseForm
from .models import Document, IngestionTask, KnowledgeBase
from .permissions import (
    can_manage_knowledge_base,
    get_visible_knowledge_base,
    visible_knowledge_bases,
)
from .services import create_uploaded_document, retry_ingestion


@login_required
def dashboard(request):
    knowledge_bases = visible_knowledge_bases(request.user).annotate(
        document_count=Count("documents", distinct=True),
        ready_count=Count("documents", filter=Q(documents__status=Document.Status.READY)),
    )
    usage = ModelUsageRecord.objects.filter(organization__memberships__user=request.user).aggregate(
        input=Sum("input_tokens"), output=Sum("output_tokens")
    )
    return render(
        request,
        "knowledge/dashboard.html",
        {
            "knowledge_bases": knowledge_bases,
            "usage": usage,
            "knowledge_base_form": KnowledgeBaseForm(),
        },
    )


@login_required
@require_POST
def knowledge_base_create(request):
    form = KnowledgeBaseForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "knowledge/dashboard.html",
            {"knowledge_bases": visible_knowledge_bases(request.user), "knowledge_base_form": form},
            status=400,
        )
    membership = request.user.organization_memberships.filter(
        role__in=[Membership.Role.OWNER, Membership.Role.EDITOR]
    ).first()
    if membership is None:
        return HttpResponseBadRequest("当前账号没有创建知识库的权限")
    knowledge_base = KnowledgeBase.objects.create(
        organization=membership.organization,
        name=form.cleaned_data["name"],
        description=form.cleaned_data["description"],
        access_scope=form.cleaned_data["access_scope"],
        created_by=request.user,
    )
    record_audit(
        organization=membership.organization,
        actor=request.user,
        event="knowledge_base.created",
        target=knowledge_base,
    )
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
def knowledge_base_detail(request, knowledge_base_id):
    knowledge_base = get_visible_knowledge_base(request.user, knowledge_base_id)
    documents = knowledge_base.documents.select_related("current_version").all()
    tasks = (
        IngestionTask.objects.filter(document_version__document__knowledge_base=knowledge_base)
        .select_related("document_version__document")
        .order_by("-created_at")
    )
    task_by_document = {}
    for task in tasks:
        task_by_document.setdefault(task.document_version.document_id, task)
    recent_conversation = (
        Conversation.objects.filter(knowledge_base=knowledge_base, created_by=request.user)
        .prefetch_related("messages__sources__document_version__document")
        .first()
    )
    return render(
        request,
        "knowledge/detail.html",
        {
            "knowledge_base": knowledge_base,
            "documents": documents,
            "task_by_document": task_by_document,
            "upload_form": DocumentBatchUploadForm(),
            "batch_upload_limit": settings.MAX_BATCH_UPLOAD_COUNT,
            "conversation": recent_conversation,
        },
    )


@login_required
@require_POST
def document_upload(request, knowledge_base_id):
    knowledge_base = get_visible_knowledge_base(request.user, knowledge_base_id)
    if not can_manage_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("你没有上传文档的权限")
    form = DocumentBatchUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, form.errors["files"][0])
        return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)
    for uploaded_file in form.cleaned_data["files"]:
        create_uploaded_document(
            user=request.user,
            knowledge_base=knowledge_base,
            uploaded_file=uploaded_file,
        )
    messages.success(request, f"已添加 {len(form.cleaned_data['files'])} 个文档，正在后台解析。")
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
@require_POST
def ingestion_retry(request, task_id):
    task = get_object_or_404(
        IngestionTask.objects.select_related("document_version__document__knowledge_base"),
        pk=task_id,
    )
    knowledge_base = get_visible_knowledge_base(
        request.user, task.document_version.document.knowledge_base_id
    )
    if not can_manage_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("你没有重试任务的权限")
    try:
        retry_ingestion(task)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    record_audit(
        organization=knowledge_base.organization,
        actor=request.user,
        event="ingestion.retried",
        target=task,
    )
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
def document_download(request, document_id):
    document = get_object_or_404(Document.objects.select_related("knowledge_base"), pk=document_id)
    get_visible_knowledge_base(request.user, document.knowledge_base_id)
    return FileResponse(
        document.source_file.open("rb"), as_attachment=True, filename=document.source_file.name
    )
