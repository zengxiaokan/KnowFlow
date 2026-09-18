from django.urls import path

from .consumers import IngestionTaskConsumer

websocket_urlpatterns = [
    path("ws/tasks/<uuid:task_id>/", IngestionTaskConsumer.as_asgi()),
]
