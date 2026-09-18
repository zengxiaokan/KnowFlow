import re
import time

from celery import shared_task
from django.utils import timezone

from apps.chat.models import ModelUsageRecord
from apps.chat.tasks import _retrieve_sources, select_context_chunks
from apps.knowledge.providers import get_chat_provider

from .models import WorkflowRun, WorkflowStepRun


def _render(template: str, context: dict) -> str:
    def replacement(match):
        return str(context.get(match.group(1).strip(), ""))

    return re.sub(r"{{\s*([^}]+)\s*}}", replacement, template or "")


@shared_task(bind=True, max_retries=1)
def execute_workflow(self, run_id: str):
    run = WorkflowRun.objects.select_related(
        "workflow_version__workflow__knowledge_base", "organization", "created_by"
    ).get(pk=run_id)
    if run.status == WorkflowRun.Status.SUCCEEDED:
        return {"run_id": str(run.id), "status": run.status}

    run.status = WorkflowRun.Status.RUNNING
    run.started_at = timezone.now()
    run.error_message = ""
    run.save(update_fields=["status", "started_at", "error_message"])
    context = dict(run.input_data)
    try:
        nodes = run.workflow_version.definition["nodes"]
        for ordinal, node in enumerate(nodes):
            step = WorkflowStepRun.objects.create(
                workflow_run=run,
                key=node["key"],
                node_type=node["type"],
                ordinal=ordinal,
                status=WorkflowStepRun.Status.RUNNING,
                input_data=node,
                started_at=timezone.now(),
            )
            output = _execute_node(node, context, run)
            context[node["key"]] = output
            step.status = WorkflowStepRun.Status.SUCCEEDED
            step.output_data = {"value": output}
            step.finished_at = timezone.now()
            step.save(update_fields=["status", "output_data", "finished_at"])
        run.status = WorkflowRun.Status.SUCCEEDED
        run.output_data = context
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "output_data", "finished_at"])
        return {"run_id": str(run.id), "status": run.status, "output": context}
    except Exception as exc:
        run.status = WorkflowRun.Status.FAILED
        run.error_message = str(exc)[:2000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        WorkflowStepRun.objects.filter(
            workflow_run=run, status=WorkflowStepRun.Status.RUNNING
        ).update(status=WorkflowStepRun.Status.FAILED, error_message=run.error_message)
        raise


def _execute_node(node: dict, context: dict, run: WorkflowRun):
    node_type = node["type"]
    if node_type == "input":
        return context.get(node.get("input_key", node["key"]), node.get("default", ""))
    if node_type == "prompt":
        return _render(node.get("template", ""), context)
    if node_type == "retrieve":
        workflow = run.workflow_version.workflow
        if workflow.knowledge_base_id is None:
            raise ValueError("检索节点需要绑定知识库")
        query = _render(node.get("query", "{{ input }}"), context)
        chunks = select_context_chunks(
            _retrieve_sources(workflow.knowledge_base, query), node.get("limit", 4)
        )
        return "\n\n".join(chunk.content for chunk in chunks)
    if node_type == "llm":
        provider = get_chat_provider()
        prompt = _render(node.get("prompt", ""), context)
        started = time.monotonic()
        content = "".join(
            delta.text
            for delta in provider.stream(
                [
                    {"role": "system", "content": node.get("system", "你是工作流助手。")},
                    {"role": "user", "content": prompt},
                ]
            )
            if delta.text
        )
        ModelUsageRecord.objects.create(
            organization=run.organization,
            user=run.created_by,
            provider=provider.provider_name,
            model=provider.model_name,
            kind=ModelUsageRecord.Kind.WORKFLOW,
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=max(1, len(content) // 4),
            is_estimated=True,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return content
    raise ValueError(f"未知工作流节点：{node_type}")
