import pytest
from django.contrib.auth.models import User

from apps.knowledge.models import KnowledgeBase
from apps.knowledge.permissions import visible_knowledge_bases


@pytest.mark.django_db
def test_knowledge_bases_are_scoped_to_organization():
    first = User.objects.create_user(username="first", password="test-pass-123")
    second = User.objects.create_user(username="second", password="test-pass-123")
    first_org = first.organization_memberships.get().organization
    knowledge_base = KnowledgeBase.objects.create(
        organization=first_org, name="Private", created_by=first
    )

    assert list(visible_knowledge_bases(first)) == [knowledge_base]
    assert not visible_knowledge_bases(second).filter(pk=knowledge_base.pk).exists()
