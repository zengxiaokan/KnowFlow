from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.edit import FormView

from .forms import InvitationForm, SignUpForm
from .models import Invitation, Membership
from .services import record_audit


class SignUpView(FormView):
    template_name = "registration/signup.html"
    form_class = SignUpForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect("dashboard")


@login_required
def team(request):
    membership = request.user.organization_memberships.select_related("organization").first()
    if membership is None:
        return HttpResponseBadRequest("当前账号不属于任何组织空间")
    organization = membership.organization
    return render(
        request,
        "identity/team.html",
        {
            "organization": organization,
            "membership": membership,
            "members": organization.memberships.select_related("user"),
            "invitations": organization.invitations.select_related("created_by").filter(
                accepted_at__isnull=True
            ),
            "form": InvitationForm(),
        },
    )


@login_required
@require_POST
def invitation_create(request):
    membership = request.user.organization_memberships.select_related("organization").first()
    if membership is None or membership.role != Membership.Role.OWNER:
        return HttpResponseBadRequest("只有空间所有者可以邀请成员")
    form = InvitationForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "identity/team.html",
            {
                "organization": membership.organization,
                "membership": membership,
                "members": membership.organization.memberships.select_related("user"),
                "invitations": membership.organization.invitations.filter(accepted_at__isnull=True),
                "form": form,
            },
            status=400,
        )
    invitation, created = Invitation.objects.update_or_create(
        organization=membership.organization,
        email=form.cleaned_data["email"].lower(),
        accepted_at__isnull=True,
        defaults={
            "role": form.cleaned_data["role"],
            "created_by": request.user,
            "expires_at": timezone.now() + timedelta(days=7),
        },
    )
    record_audit(
        organization=membership.organization,
        actor=request.user,
        event="member.invited",
        target=invitation,
        metadata={"email": invitation.email, "role": invitation.role, "created": created},
    )
    invite_url = request.build_absolute_uri(f"/accounts/invitations/{invitation.token}/accept/")
    messages.success(request, f"邀请链接已生成，请安全发送给成员：{invite_url}")
    return redirect("team")


@login_required
def invitation_accept(request, token):
    invitation = get_object_or_404(Invitation.objects.select_related("organization"), token=token)
    if not invitation.is_active:
        return HttpResponseBadRequest("邀请已失效或已被使用")
    if request.user.email.lower() != invitation.email.lower():
        return HttpResponseBadRequest("请使用受邀邮箱对应的账号接受邀请")
    Membership.objects.update_or_create(
        organization=invitation.organization,
        user=request.user,
        defaults={"role": invitation.role},
    )
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = request.user
    invitation.save(update_fields=["accepted_at", "accepted_by"])
    record_audit(
        organization=invitation.organization,
        actor=request.user,
        event="member.invitation_accepted",
        target=invitation,
        metadata={"role": invitation.role},
    )
    messages.success(request, f"已加入 {invitation.organization.name}")
    return redirect("dashboard")
