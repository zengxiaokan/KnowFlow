from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic.edit import FormView

from .forms import InvitationForm, MemberRoleForm, SignUpForm
from .models import AuditLog, Invitation, Membership
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
            "member_role_choices": Membership.Role.choices,
        },
    )


def _organization_membership(request):
    return request.user.organization_memberships.select_related("organization").first()


def _owner_membership(request):
    membership = _organization_membership(request)
    if membership is None:
        return None, HttpResponseBadRequest("当前账号不属于任何组织空间")
    if membership.role != Membership.Role.OWNER:
        return membership, HttpResponseForbidden("只有空间所有者可以管理团队成员")
    return membership, None


@login_required
@require_POST
def invitation_create(request):
    membership, error = _owner_membership(request)
    if error:
        return error
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
                "member_role_choices": Membership.Role.choices,
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
@require_POST
def member_update(request, membership_id):
    owner_membership, error = _owner_membership(request)
    if error:
        return error
    target = get_object_or_404(
        Membership.objects.select_related("organization", "user"),
        pk=membership_id,
        organization_id=owner_membership.organization_id,
    )
    if target.user_id == request.user.id:
        return HttpResponseForbidden("不能修改自己的组织角色")

    form = MemberRoleForm(request.POST)
    if not form.is_valid():
        messages.error(request, "请选择有效的组织角色。")
        return redirect("team")

    new_role = form.cleaned_data["role"]
    if target.role == new_role:
        messages.info(request, "成员角色没有变化。")
        return redirect("team")
    if (
        target.role == Membership.Role.OWNER
        and new_role != Membership.Role.OWNER
        and not Membership.objects.filter(
            organization_id=owner_membership.organization_id,
            role=Membership.Role.OWNER,
        ).exclude(pk=target.pk).exists()
    ):
        return HttpResponseForbidden("组织至少需要保留一个所有者")

    old_role = target.role
    with transaction.atomic():
        target.role = new_role
        target.save(update_fields=["role"])
        record_audit(
            organization=owner_membership.organization,
            actor=request.user,
            event="member.role_changed",
            target=target,
            metadata={
                "username": target.user.username,
                "user_id": target.user_id,
                "old_role": old_role,
                "new_role": new_role,
            },
        )
    messages.success(
        request,
        f"已将 {target.user.username} 的角色调整为 {target.get_role_display()}。",
    )
    return redirect("team")


@login_required
@require_POST
def member_remove(request, membership_id):
    owner_membership, error = _owner_membership(request)
    if error:
        return error
    target = get_object_or_404(
        Membership.objects.select_related("organization", "user"),
        pk=membership_id,
        organization_id=owner_membership.organization_id,
    )
    if target.user_id == request.user.id:
        return HttpResponseForbidden("不能移除自己的组织成员资格")
    if (
        target.role == Membership.Role.OWNER
        and not Membership.objects.filter(
            organization_id=owner_membership.organization_id,
            role=Membership.Role.OWNER,
        ).exclude(pk=target.pk).exists()
    ):
        return HttpResponseForbidden("组织至少需要保留一个所有者")

    username = target.user.username
    with transaction.atomic():
        record_audit(
            organization=owner_membership.organization,
            actor=request.user,
            event="member.removed",
            target=target,
            metadata={
                "username": target.user.username,
                "user_id": target.user_id,
                "old_role": target.role,
            },
        )
        target.delete()
    messages.success(request, f"已移除成员 {username}。")
    return redirect("team")


@login_required
def audit_log(request):
    membership, error = _owner_membership(request)
    if error:
        return error
    logs = (
        AuditLog.objects.filter(organization_id=membership.organization_id)
        .select_related("actor")[:200]
    )
    return render(
        request,
        "identity/audit_log.html",
        {"organization": membership.organization, "membership": membership, "logs": logs},
    )


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
