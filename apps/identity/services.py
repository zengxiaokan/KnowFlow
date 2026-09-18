from .models import AuditLog


def record_audit(*, organization, actor, event, target, metadata=None):
    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        event=event,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        metadata=metadata or {},
    )
