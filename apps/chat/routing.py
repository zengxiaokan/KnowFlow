from django.urls import path

from .consumers import ConversationConsumer

websocket_urlpatterns = [
    path("ws/conversations/<uuid:conversation_id>/", ConversationConsumer.as_asgi()),
]
