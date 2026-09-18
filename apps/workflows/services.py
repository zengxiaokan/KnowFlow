from django.db import transaction

from apps.identity.models import Membership
from apps.identity.services import record_audit
from apps.knowledge.permissions import get_visible_knowledge_base, visible_knowledge_bases

from .models import Workflow, WorkflowRun, WorkflowVersion
from .tasks import execute_workflow

ALLOWED_NODE_TYPES = {"input", "retrieve", "prompt", "llm"}


def validate_definition(definition: dict) -> dict:
    nodes = definition.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("工作流定义需要至少一个 nodes 节点")
    keys = set()
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") not in ALLOWED_NODE_TYPES:
            raise ValueError("节点类型仅支持 input、retrieve、prompt、llm")
        key = node.get("key")
        if not isinstance(key, str) or not key or key in keys:
            raise ValueError("每个节点需要唯一的 key")
        keys.add(key)
    return definition


def create_workflow(*, user, organization, knowledge_base_id, name, description, definition):
    knowledge_base = (
        get_visible_knowledge_base(user, knowledge_base_id) if knowledge_base_id else None
    )
    if knowledge_base and knowledge_base.organization_id != organization.id:
        raise ValueError("知识库不属于当前空间")
    definition = validate_definition(definition)
    with transaction.atomic():
        workflow = Workflow.objects.create(
            organization=organization,
            knowledge_base=knowledge_base,
            name=name,
            description=description,
            created_by=user,
        )
        WorkflowVersion.objects.create(
            workflow=workflow, number=1, definition=definition, is_published=True
        )
        record_audit(
            organization=organization,
            actor=user,
            event="workflow.created",
            target=workflow,
        )
    return workflow


def launch_workflow(*, user, workflow: Workflow, input_data: dict):
    can_run = Membership.objects.filter(
        organization=workflow.organization,
        user=user,
        role__in=[Membership.Role.OWNER, Membership.Role.EDITOR],
    ).exists()
    if not can_run:
        raise ValueError("当前账号没有运行工作流的权限")
    if (
        workflow.knowledge_base_id
        and not visible_knowledge_bases(user).filter(pk=workflow.knowledge_base_id).exists()
    ):
        raise ValueError("你没有访问此工作流知识库的权限")
    version = workflow.versions.filter(is_published=True).first()
    if version is None:
        raise ValueError("工作流没有已发布版本")
    run = WorkflowRun.objects.create(
        workflow_version=version,
        organization=workflow.organization,
        created_by=user,
        input_data=input_data or {},
    )
    result = execute_workflow.delay(str(run.id))
    run.celery_task_id = result.id
    run.save(update_fields=["celery_task_id"])
    record_audit(
        organization=workflow.organization,
        actor=user,
        event="workflow.run_requested",
        target=run,
    )
    return run


def retry_workflow(*, user, run: WorkflowRun):
    if run.status != WorkflowRun.Status.FAILED:
        raise ValueError("只有失败的工作流运行可以重试")
    workflow = run.workflow_version.workflow
    can_run = Membership.objects.filter(
        organization=run.organization,
        user=user,
        role__in=[Membership.Role.OWNER, Membership.Role.EDITOR],
    ).exists()
    if not can_run:
        raise ValueError("当前账号没有重试工作流的权限")
    if (
        workflow.knowledge_base_id
        and not visible_knowledge_bases(user).filter(pk=workflow.knowledge_base_id).exists()
    ):
        raise ValueError("你没有访问此工作流知识库的权限")
    with transaction.atomic():
        run.step_runs.all().delete()
        run.status = WorkflowRun.Status.PENDING
        run.output_data = {}
        run.error_message = ""
        run.started_at = None
        run.finished_at = None
        run.save(
            update_fields=[
                "status",
                "output_data",
                "error_message",
                "started_at",
                "finished_at",
            ]
        )
        result = execute_workflow.delay(str(run.id))
        run.celery_task_id = result.id
        run.save(update_fields=["celery_task_id"])
        record_audit(
            organization=run.organization,
            actor=user,
            event="workflow.run_retried",
            target=run,
        )
    return run
