from django.contrib import admin

from .models import Workflow, WorkflowRun, WorkflowStepRun, WorkflowVersion


class WorkflowVersionInline(admin.TabularInline):
    model = WorkflowVersion
    extra = 0


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "knowledge_base", "updated_at")
    inlines = [WorkflowVersionInline]


class WorkflowStepRunInline(admin.TabularInline):
    model = WorkflowStepRun
    extra = 0
    readonly_fields = ("key", "node_type", "status", "input_data", "output_data", "error_message")


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = ("id", "workflow_version", "status", "created_at")
    inlines = [WorkflowStepRunInline]
