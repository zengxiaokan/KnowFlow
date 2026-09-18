from django.contrib import admin

from .models import (
    Chunk,
    Document,
    DocumentVersion,
    IngestionTask,
    KnowledgeBase,
    KnowledgeBaseMembership,
)


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    readonly_fields = ("number", "extracted_characters", "metadata", "created_at")


class KnowledgeBaseMembershipInline(admin.TabularInline):
    model = KnowledgeBaseMembership
    extra = 0


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "access_scope", "created_by", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("organization",)
    inlines = [KnowledgeBaseMembershipInline]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "knowledge_base", "file_type", "status", "updated_at")
    list_filter = ("status", "file_type")
    search_fields = ("title",)
    inlines = [DocumentVersionInline]


@admin.register(IngestionTask)
class IngestionTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "document_version", "status", "stage", "progress", "attempt_count")
    list_filter = ("status", "stage")
    readonly_fields = ("id", "created_at", "started_at", "finished_at")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "knowledge_base", "document_version", "ordinal", "heading")
    search_fields = ("content", "heading")
