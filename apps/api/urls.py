from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ConversationViewSet,
    DocumentViewSet,
    IngestionTaskViewSet,
    KnowledgeBaseViewSet,
    UsageViewSet,
    WorkflowViewSet,
)

router = DefaultRouter()
router.register("knowledge-bases", KnowledgeBaseViewSet, basename="knowledge-base")
router.register("documents", DocumentViewSet, basename="document")
router.register("tasks", IngestionTaskViewSet, basename="task")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("usage", UsageViewSet, basename="usage")
router.register("workflows", WorkflowViewSet, basename="workflow")

urlpatterns = [path("", include(router.urls))]
