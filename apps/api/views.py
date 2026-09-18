from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.chat.models import Conversation, ModelUsageRecord
from apps.chat.services import submit_question
from apps.identity.models import Membership
from apps.knowledge.models import Document, IngestionTask
from apps.knowledge.permissions import (
    can_manage_knowledge_base,
    get_visible_knowledge_base,
    visible_knowledge_bases,
)
from apps.knowledge.services import create_uploaded_document, retry_ingestion
from apps.workflows.models import Workflow
from apps.workflows.services import launch_workflow

from .serializers import (
    ConversationSerializer,
    DocumentSerializer,
    IngestionTaskSerializer,
    KnowledgeBaseSerializer,
    ModelUsageSerializer,
    WorkflowRunSerializer,
    WorkflowSerializer,
)


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeBaseSerializer

    def get_queryset(self):
        return visible_knowledge_bases(self.request.user)

    def perform_create(self, serializer):
        membership = self.request.user.organization_memberships.filter(
            role__in=[Membership.Role.OWNER, Membership.Role.EDITOR]
        ).first()
        if membership is None:
            raise PermissionError("没有可写入的组织空间")
        serializer.save(organization=membership.organization, created_by=self.request.user)

    def perform_update(self, serializer):
        if not can_manage_knowledge_base(self.request.user, serializer.instance):
            raise PermissionDenied("没有修改知识库的权限")
        serializer.save()

    def perform_destroy(self, instance):
        if not can_manage_knowledge_base(self.request.user, instance):
            raise PermissionDenied("没有删除知识库的权限")
        instance.delete()


class DocumentViewSet(mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Document.objects.filter(
            knowledge_base__in=visible_knowledge_bases(self.request.user)
        )

    def create(self, request, *args, **kwargs):
        knowledge_base = get_visible_knowledge_base(
            request.user, request.data.get("knowledge_base")
        )
        if not can_manage_knowledge_base(request.user, knowledge_base):
            return Response({"detail": "没有上传权限"}, status=status.HTTP_403_FORBIDDEN)
        try:
            document, task = create_uploaded_document(
                user=request.user,
                knowledge_base=knowledge_base,
                uploaded_file=request.FILES.get("source_file"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payload = self.get_serializer(document).data
        payload["ingestion_task_id"] = task.id
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        document = self.get_object()
        task = document.versions.first().ingestion_tasks.first()
        if task is None:
            return Response({"detail": "找不到处理任务"}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_knowledge_base(request.user, document.knowledge_base):
            return Response({"detail": "没有重试权限"}, status=status.HTTP_403_FORBIDDEN)
        try:
            retry_ingestion(task)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(IngestionTaskSerializer(task).data)


class IngestionTaskViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = IngestionTaskSerializer

    def get_queryset(self):
        return IngestionTask.objects.filter(
            document_version__document__knowledge_base__in=visible_knowledge_bases(
                self.request.user
            )
        )


class ConversationViewSet(
    mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(
            organization__memberships__user=self.request.user, created_by=self.request.user
        ).prefetch_related("messages__sources__document_version__document")

    @action(detail=False, methods=["post"])
    def ask(self, request):
        try:
            conversation, assistant_message = submit_question(
                user=request.user,
                knowledge_base_id=request.data.get("knowledge_base"),
                content=request.data.get("content", ""),
                conversation_id=request.data.get("conversation_id"),
            )
        except (ValueError, Conversation.DoesNotExist) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "conversation_id": conversation.id,
                "assistant_message_id": assistant_message.id,
                "websocket_url": f"/ws/conversations/{conversation.id}/",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class UsageViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ModelUsageSerializer

    def get_queryset(self):
        return ModelUsageRecord.objects.filter(organization__memberships__user=self.request.user)


class WorkflowViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = WorkflowSerializer

    def get_queryset(self):
        return (
            Workflow.objects.filter(
                organization__memberships__user=self.request.user,
            )
            .filter(
                Q(knowledge_base__isnull=True)
                | Q(knowledge_base__in=visible_knowledge_bases(self.request.user))
            )
            .distinct()
        )

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        workflow = self.get_object()
        try:
            run = launch_workflow(
                user=request.user, workflow=workflow, input_data=request.data.get("input_data", {})
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WorkflowRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)
