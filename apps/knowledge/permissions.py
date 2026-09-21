from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.identity.models import Membership

from .models import KnowledgeBase


def organization_ids_for(user):
    return user.organization_memberships.values_list("organization_id", flat=True)


def visible_knowledge_bases(user):
    organization_ids = organization_ids_for(user)
    return (
        KnowledgeBase.objects.filter(organization_id__in=organization_ids)
        .filter(
            Q(access_scope=KnowledgeBase.AccessScope.ORGANIZATION)
            | Q(memberships__user=user)
            | Q(
                organization__memberships__user=user,
                organization__memberships__role=Membership.Role.OWNER,
            )
        )
        .distinct()
    )


def get_visible_knowledge_base(user, pk):
    return get_object_or_404(visible_knowledge_bases(user), pk=pk)


def can_manage_knowledge_base(user, knowledge_base) -> bool:
    organization_membership = Membership.objects.filter(
        organization=knowledge_base.organization, user=user
    )
    if not organization_membership.exists():
        return False
    if organization_membership.filter(role=Membership.Role.OWNER).exists():
        return True
    if knowledge_base.memberships.filter(user=user, role="manager").exists():
        return True
    return (
        knowledge_base.access_scope == KnowledgeBase.AccessScope.ORGANIZATION
        and organization_membership.filter(role=Membership.Role.EDITOR).exists()
    )


def can_delete_knowledge_base(user, knowledge_base) -> bool:
    return Membership.objects.filter(
        organization=knowledge_base.organization,
        user=user,
        role=Membership.Role.OWNER,
    ).exists()
