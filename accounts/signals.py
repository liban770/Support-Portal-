from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def sync_role_group(sender, instance, **kwargs):
    """Keep each user in exactly one Django Group matching their portal role.

    Authorization is enforced in `cases.permissions` / `accounts.decorators`;
    groups mirror roles so standard Django tooling and reports stay consistent.
    """
    role_groups = {label for _, label in User.Role.choices}
    target_name = instance.get_role_display()
    target, _ = Group.objects.get_or_create(name=target_name)
    current = set(instance.groups.values_list("name", flat=True))
    stale = (current & role_groups) - {target_name}
    if stale:
        instance.groups.remove(*Group.objects.filter(name__in=stale))
    if target_name not in current:
        instance.groups.add(target)
