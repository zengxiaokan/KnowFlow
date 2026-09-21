from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Conversation, Message
from .services import regenerate_answer, submit_question


@login_required
@require_POST
def ask_question(request, knowledge_base_id):
    try:
        conversation, assistant_message = submit_question(
            user=request.user,
            knowledge_base_id=knowledge_base_id,
            content=request.POST.get("content", ""),
            conversation_id=request.POST.get("conversation_id") or None,
        )
    except (ValueError, Conversation.DoesNotExist) as exc:
        return HttpResponseBadRequest(str(exc))
    return JsonResponse(
        {
            "conversation_id": str(conversation.id),
            "assistant_message_id": str(assistant_message.id),
            "websocket_url": f"/ws/conversations/{conversation.id}/",
        },
        status=202,
    )


@login_required
@require_POST
def regenerate(request, assistant_message_id):
    try:
        conversation, assistant_message = regenerate_answer(
            user=request.user, assistant_message_id=assistant_message_id
        )
    except (Message.DoesNotExist, PermissionError, ValueError) as exc:
        return HttpResponseBadRequest(str(exc))
    url = reverse("knowledge_base_detail", args=[conversation.knowledge_base_id])
    return redirect(f"{url}?conversation={conversation.id}")


def _owned_conversation(request, conversation_id):
    return get_object_or_404(Conversation, pk=conversation_id, created_by=request.user)


@login_required
@require_POST
def conversation_rename(request, conversation_id):
    conversation = _owned_conversation(request, conversation_id)
    title = request.POST.get("title", "").strip()[:160]
    if not title:
        return HttpResponseBadRequest("会话名称不能为空")
    conversation.title = title
    conversation.save(update_fields=["title", "updated_at"])
    return redirect(
        f"{reverse('knowledge_base_detail', args=[conversation.knowledge_base_id])}?conversation={conversation.id}"
    )


@login_required
@require_POST
def conversation_delete(request, conversation_id):
    conversation = _owned_conversation(request, conversation_id)
    knowledge_base_id = conversation.knowledge_base_id
    conversation.delete()
    return redirect(
        f"{reverse('knowledge_base_detail', args=[knowledge_base_id])}?conversation=new"
    )


@login_required
def conversation_export(request, conversation_id):
    conversation = _owned_conversation(request, conversation_id)
    lines = [f"# {conversation.title or 'KnowFlow 对话记录'}", ""]
    for message in conversation.messages.all():
        role = "用户" if message.role == Message.Role.USER else "助手"
        lines.extend([f"## {role}", "", message.content, ""])
    response = HttpResponse("\n".join(lines), content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="knowflow-conversation.md"'
    return response
