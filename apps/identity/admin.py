from django.contrib import admin

from .models import AuditLog, Invitation, Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    inlines = [MembershipInline]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "role", "expires_at", "accepted_at")
    list_filter = ("role", "accepted_at")
    search_fields = ("email",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "organization", "actor", "event", "target_type", "target_id")
    list_filter = ("event",)
    readonly_fields = ("organization", "actor", "event", "target_type", "target_id", "metadata")
