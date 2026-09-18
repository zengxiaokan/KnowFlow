from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.identity import views as identity_views
from apps.identity.forms import SignInForm
from apps.identity.views import SignUpView
from apps.knowledge.views import dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard, name="dashboard"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=SignInForm),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", SignUpView.as_view(), name="signup"),
    path("team/", identity_views.team, name="team"),
    path(
        "accounts/invitations/<uuid:token>/accept/",
        identity_views.invitation_accept,
        name="invitation_accept",
    ),
    path("team/invitations/", identity_views.invitation_create, name="invitation_create"),
    path("knowledge/", include("apps.knowledge.urls")),
    path("workflows/", include("apps.workflows.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
