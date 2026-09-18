from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST

from .models import Conversation
from .services import submit_question


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
