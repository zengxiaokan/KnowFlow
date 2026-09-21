from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
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
