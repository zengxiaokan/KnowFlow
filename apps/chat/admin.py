from django.contrib import admin

from .models import Conversation, Message, ModelUsageRecord


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "knowledge_base", "created_by", "updated_at")
    inlines = [MessageInline]


@admin.register(ModelUsageRecord)
class ModelUsageRecordAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "organization",
        "kind",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
    )
    list_filter = ("kind", "provider", "is_estimated")
