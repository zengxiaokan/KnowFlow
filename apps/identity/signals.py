from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Membership, Organization


@receiver(post_save, sender=get_user_model())
def create_personal_organization(sender, instance, created, **kwargs):
    if not created:
        return
    label = instance.get_username() or f"user-{instance.pk}"
    organization = Organization.objects.create(
        name=f"{label} 的空间", slug=f"{slugify(label) or 'user'}-{instance.pk}"
    )
    Membership.objects.create(organization=organization, user=instance, role=Membership.Role.OWNER)
