from django.urls import path

from . import views

urlpatterns = [
    path("", views.workflow_list, name="workflow_list"),
    path("create/", views.workflow_create, name="workflow_create"),
    path("<int:workflow_id>/run/", views.workflow_run, name="workflow_run"),
    path("runs/<uuid:run_id>/retry/", views.workflow_run_retry, name="workflow_run_retry"),
]
