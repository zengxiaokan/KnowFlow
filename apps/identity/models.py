import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    organization = models.ForeignKey(
        Organization, related_name="memberships", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="organization_memberships", on_delete=models.CASCADE
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.OWNER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="uniq_org_member")
        ]

    def __str__(self):
        return f"{self.organization} / {self.user} ({self.role})"


class Invitation(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        Organization, related_name="invitations", on_delete=models.CASCADE
    )
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Membership.Role.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="sent_invitations",
        on_delete=models.PROTECT,
    )
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=models.Q(accepted_at__isnull=True),
                name="uniq_pending_invitation_per_email",
            )
        ]
        ordering = ["-created_at"]

    @property
    def is_active(self):
        return self.accepted_at is None and self.expires_at > timezone.now()


class AuditLog(models.Model):
    organization = models.ForeignKey(
        Organization, related_name="audit_logs", on_delete=models.CASCADE
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="audit_logs",
        on_delete=models.SET_NULL,
    )
    event = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "created_at"])]
        ordering = ["-created_at"]
