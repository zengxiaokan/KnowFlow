from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.identity.models import Membership
from apps.knowledge.permissions import visible_knowledge_bases

from .forms import WorkflowCreateForm
from .models import Workflow, WorkflowRun
from .services import create_workflow, launch_workflow, retry_workflow


@login_required
def workflow_list(request):
    organization_ids = request.user.organization_memberships.values_list(
        "organization_id", flat=True
    )
    workflows = (
        Workflow.objects.filter(organization_id__in=organization_ids)
        .filter(
            Q(knowledge_base__isnull=True)
            | Q(knowledge_base__in=visible_knowledge_bases(request.user))
        )
        .select_related("knowledge_base")
    )
    for workflow in workflows:
        version = workflow.versions.order_by("-number").first()
        workflow.input_fields = []
        for node in version.definition.get("nodes", []) if version else []:
            if node.get("type") == "input":
                name = node.get("input_key", node["key"])
                workflow.input_fields.append({"name": name, "label": node.get("label", name)})
    runs = WorkflowRun.objects.filter(
        organization_id__in=organization_ids,
        workflow_version__workflow__in=workflows,
    ).select_related("workflow_version__workflow")[:10]
    form = WorkflowCreateForm(user=request.user)
    return render(
        request,
        "workflows/list.html",
        {"workflows": workflows, "runs": runs, "form": form},
    )


@login_required
@require_POST
def workflow_create(request):
    form = WorkflowCreateForm(request.POST, user=request.user)
    if not form.is_valid():
        organization_ids = request.user.organization_memberships.values_list(
            "organization_id", flat=True
        )
        workflows = Workflow.objects.filter(organization_id__in=organization_ids).filter(
            Q(knowledge_base__isnull=True)
            | Q(knowledge_base__in=visible_knowledge_bases(request.user))
        )
        return render(
            request,
            "workflows/list.html",
            {
                "workflows": workflows,
                "runs": WorkflowRun.objects.filter(
                    organization_id__in=organization_ids,
                    workflow_version__workflow__in=workflows,
                )[:10],
                "form": form,
            },
            status=400,
        )
    membership = request.user.organization_memberships.filter(
        role__in=[Membership.Role.OWNER, Membership.Role.EDITOR]
    ).first()
    if membership is None:
        return HttpResponseBadRequest("当前账号没有创建工作流的权限")
    try:
        create_workflow(
            user=request.user,
            organization=membership.organization,
            knowledge_base_id=form.cleaned_data["knowledge_base"] or None,
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            definition=form.definition(),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return redirect("workflow_list")


@login_required
@require_POST
def workflow_run(request, workflow_id):
    workflow = get_object_or_404(
        Workflow.objects.filter(organization__memberships__user=request.user).distinct(),
        pk=workflow_id,
    )
    input_data = {
        key: value.strip()
        for key, value in request.POST.items()
        if key != "csrfmiddlewaretoken" and value.strip()
    }
    if not input_data:
        return HttpResponseBadRequest("请至少填写一个输入值")
    launch_workflow(user=request.user, workflow=workflow, input_data=input_data)
    return redirect("workflow_list")


@login_required
def workflow_run_detail(request, run_id):
    run = get_object_or_404(
        WorkflowRun.objects.select_related("workflow_version__workflow").prefetch_related(
            "step_runs"
        ),
        pk=run_id,
        organization__memberships__user=request.user,
    )
    return render(request, "workflows/run_detail.html", {"run": run})


@login_required
@require_POST
def workflow_run_retry(request, run_id):
    run = get_object_or_404(
        WorkflowRun.objects.filter(organization__memberships__user=request.user).distinct(),
        pk=run_id,
    )
    try:
        retry_workflow(user=request.user, run=run)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return redirect("workflow_list")
