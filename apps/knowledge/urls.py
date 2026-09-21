from django.urls import path

from apps.chat.views import (
    ask_question,
    conversation_delete,
    conversation_export,
    conversation_rename,
    regenerate,
)

from . import views

urlpatterns = [
    path("create/", views.knowledge_base_create, name="knowledge_base_create"),
    path("<int:knowledge_base_id>/", views.knowledge_base_detail, name="knowledge_base_detail"),
    path(
        "<int:knowledge_base_id>/update/",
        views.knowledge_base_update,
        name="knowledge_base_update",
    ),
    path(
        "<int:knowledge_base_id>/delete/",
        views.knowledge_base_delete,
        name="knowledge_base_delete",
    ),
    path("<int:knowledge_base_id>/upload/", views.document_upload, name="document_upload"),
    path("<int:knowledge_base_id>/ask/", ask_question, name="ask_question"),
    path("answers/<uuid:assistant_message_id>/regenerate/", regenerate, name="regenerate_answer"),
    path(
        "conversations/<uuid:conversation_id>/rename/",
        conversation_rename,
        name="conversation_rename",
    ),
    path(
        "conversations/<uuid:conversation_id>/delete/",
        conversation_delete,
        name="conversation_delete",
    ),
    path(
        "conversations/<uuid:conversation_id>/export/",
        conversation_export,
        name="conversation_export",
    ),
    path("tasks/<uuid:task_id>/retry/", views.ingestion_retry, name="ingestion_retry"),
    path("documents/<int:document_id>/update/", views.document_update, name="document_update"),
    path("documents/<int:document_id>/rename/", views.document_rename, name="document_rename"),
    path("documents/<int:document_id>/delete/", views.document_delete, name="document_delete"),
    path(
        "documents/<int:document_id>/download/", views.document_download, name="document_download"
    ),
]
