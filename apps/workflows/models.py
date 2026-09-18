import uuid

from django.conf import settings
from django.db import models

from apps.identity.models import Organization
from apps.knowledge.models import KnowledgeBase


class Workflow(models.Model):
    organization = models.ForeignKey(
        Organization, related_name="workflows", on_delete=models.CASCADE
    )
    knowledge_base = models.ForeignKey(
        KnowledgeBase, related_name="workflows", null=True, blank=True, on_delete=models.SET_NULL
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="created_workflows", on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_workflow_name_per_organization"
            )
        ]
        ordering = ["name"]


class WorkflowVersion(models.Model):
    workflow = models.ForeignKey(Workflow, related_name="versions", on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    definition = models.JSONField(default=dict)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "number"], name="uniq_workflow_version_number"
            )
        ]
        ordering = ["-number"]


class WorkflowRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_version = models.ForeignKey(
        WorkflowVersion, related_name="runs", on_delete=models.PROTECT
    )
    organization = models.ForeignKey(
        Organization, related_name="workflow_runs", on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="workflow_runs", on_delete=models.PROTECT
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class WorkflowStepRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    workflow_run = models.ForeignKey(
        WorkflowRun, related_name="step_runs", on_delete=models.CASCADE
    )
    key = models.CharField(max_length=120)
    node_type = models.CharField(max_length=32)
    ordinal = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_run", "key"], name="uniq_workflow_run_step_key"
            )
        ]
        ordering = ["ordinal"]
