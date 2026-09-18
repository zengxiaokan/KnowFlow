# ruff: noqa: E402
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from apps.chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns  # noqa: E402
from apps.knowledge.routing import (
    websocket_urlpatterns as knowledge_websocket_urlpatterns,
)  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(knowledge_websocket_urlpatterns + chat_websocket_urlpatterns)
        ),
    }
)
