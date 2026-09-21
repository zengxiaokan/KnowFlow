from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.chat.models import Conversation, ModelUsageRecord
from apps.identity.models import Membership
from apps.identity.services import record_audit

from .forms import DocumentBatchUploadForm, DocumentRenameForm, KnowledgeBaseForm
from .models import Chunk, Document, IngestionTask, KnowledgeBase
from .permissions import (
    can_delete_knowledge_base,
    can_manage_knowledge_base,
    get_visible_knowledge_base,
    visible_knowledge_bases,
)
from .services import (
    create_document_version,
    create_uploaded_document,
    delete_document,
    delete_knowledge_base,
    retry_ingestion,
)


@login_required
def dashboard(request):
    knowledge_bases = visible_knowledge_bases(request.user).annotate(
        document_count=Count("documents", distinct=True),
        ready_count=Count("documents", filter=Q(documents__status=Document.Status.READY)),
    )
    usage = ModelUsageRecord.objects.filter(organization__memberships__user=request.user).aggregate(
        input=Sum("input_tokens"), output=Sum("output_tokens")
    )
    usage_by_day = list(
        ModelUsageRecord.objects.filter(organization__memberships__user=request.user)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(tokens=Sum("input_tokens") + Sum("output_tokens"))
        .order_by("day")
    )[-14:]
    max_daily_tokens = max((item["tokens"] or 0 for item in usage_by_day), default=1)
    for item in usage_by_day:
        item["height"] = max(6, round((item["tokens"] or 0) / max_daily_tokens * 100))
    return render(
        request,
        "knowledge/dashboard.html",
        {
            "knowledge_bases": knowledge_bases,
            "usage": usage,
            "knowledge_base_form": KnowledgeBaseForm(),
            "usage_by_day": usage_by_day,
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
        assistant_prompt=form.cleaned_data["assistant_prompt"],
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
    documents = knowledge_base.documents.select_related("current_version").prefetch_related(
        "versions"
    )
    tasks = (
        IngestionTask.objects.filter(document_version__document__knowledge_base=knowledge_base)
        .select_related("document_version__document")
        .order_by("-created_at")
    )
    task_by_document = {}
    for task in tasks:
        task_by_document.setdefault(task.document_version.document_id, task)
    conversations = Conversation.objects.filter(
        knowledge_base=knowledge_base, created_by=request.user
    ).prefetch_related("messages__sources__document_version__document")
    requested_conversation = request.GET.get("conversation")
    if requested_conversation and requested_conversation != "new":
        recent_conversation = get_object_or_404(conversations, pk=requested_conversation)
    elif requested_conversation == "new":
        recent_conversation = None
    else:
        recent_conversation = conversations.first()
    query = request.GET.get("q", "").strip()
    search_results = []
    if query:
        search_results = list(
            Chunk.objects.filter(
                knowledge_base=knowledge_base,
                document_version__document__current_version=F("document_version"),
                content__icontains=query,
            ).select_related("document_version__document")[:30]
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
            "conversations": conversations,
            "knowledge_base_form": KnowledgeBaseForm(
                initial={
                    "name": knowledge_base.name,
                    "description": knowledge_base.description,
                    "assistant_prompt": knowledge_base.assistant_prompt,
                    "access_scope": knowledge_base.access_scope,
                }
            ),
            "can_delete_knowledge_base": can_delete_knowledge_base(request.user, knowledge_base),
            "search_query": query,
            "search_results": search_results,
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
        existing = knowledge_base.documents.filter(
            title=Path(uploaded_file.name).stem[:255]
        ).first()
        if existing:
            create_document_version(
                user=request.user, document=existing, uploaded_file=uploaded_file
            )
        else:
            create_uploaded_document(
                user=request.user, knowledge_base=knowledge_base, uploaded_file=uploaded_file
            )
    messages.success(request, f"已添加 {len(form.cleaned_data['files'])} 个文档，正在后台解析。")
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
@require_POST
def document_update(request, document_id):
    document = get_object_or_404(Document.objects.select_related("knowledge_base"), pk=document_id)
    knowledge_base = get_visible_knowledge_base(request.user, document.knowledge_base_id)
    if not can_manage_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("你没有更新文档的权限")
    try:
        create_document_version(
            user=request.user,
            document=document,
            uploaded_file=request.FILES.get("file"),
        )
    except (ValueError, AttributeError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"已创建《{document.title}》的新版本，正在后台解析。")
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
@require_POST
def document_rename(request, document_id):
    document = get_object_or_404(Document.objects.select_related("knowledge_base"), pk=document_id)
    knowledge_base = get_visible_knowledge_base(request.user, document.knowledge_base_id)
    if not can_manage_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("你没有重命名文档的权限")
    form = DocumentRenameForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["title"][0])
    else:
        document.title = form.cleaned_data["title"].strip()
        document.save(update_fields=["title", "updated_at"])
        record_audit(
            organization=knowledge_base.organization,
            actor=request.user,
            event="document.renamed",
            target=document,
        )
        messages.success(request, "文档名称已更新。")
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
@require_POST
def document_delete(request, document_id):
    document = get_object_or_404(Document.objects.select_related("knowledge_base"), pk=document_id)
    knowledge_base = get_visible_knowledge_base(request.user, document.knowledge_base_id)
    if not can_manage_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("你没有删除文档的权限")
    title = document.title
    delete_document(user=request.user, document=document)
    messages.success(request, f"已永久删除《{title}》及其版本、向量与任务记录。")
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
@require_POST
def knowledge_base_update(request, knowledge_base_id):
    knowledge_base = get_visible_knowledge_base(request.user, knowledge_base_id)
    if not can_manage_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("你没有修改知识库的权限")
    form = KnowledgeBaseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "请检查知识库名称和设置。")
    else:
        knowledge_base.name = form.cleaned_data["name"]
        knowledge_base.description = form.cleaned_data["description"]
        knowledge_base.assistant_prompt = form.cleaned_data["assistant_prompt"]
        knowledge_base.access_scope = form.cleaned_data["access_scope"]
        try:
            knowledge_base.save(
                update_fields=[
                    "name",
                    "description",
                    "assistant_prompt",
                    "access_scope",
                    "updated_at",
                ]
            )
        except IntegrityError:
            messages.error(request, "同一组织内已存在同名知识库。")
        else:
            record_audit(
                organization=knowledge_base.organization,
                actor=request.user,
                event="knowledge_base.updated",
                target=knowledge_base,
            )
            messages.success(request, "知识库设置已保存。")
    return redirect("knowledge_base_detail", knowledge_base_id=knowledge_base.id)


@login_required
@require_POST
def knowledge_base_delete(request, knowledge_base_id):
    knowledge_base = get_visible_knowledge_base(request.user, knowledge_base_id)
    if not can_delete_knowledge_base(request.user, knowledge_base):
        return HttpResponseBadRequest("只有组织所有者可以删除知识库")
    title = knowledge_base.name
    delete_knowledge_base(user=request.user, knowledge_base=knowledge_base)
    messages.success(request, f"已永久删除知识库《{title}》。")
    return redirect("dashboard")


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
