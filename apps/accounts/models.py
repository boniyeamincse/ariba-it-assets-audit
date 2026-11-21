from django.db import models
from django.db.models.functions import Lower
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.common.models import TimeStampedModel
from apps.locations.models import Location

class UserProfile(TimeStampedModel):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        HO_ADMIN = 'HO_ADMIN', 'HO Admin'
        FACTORY_ADMIN = 'FACTORY_ADMIN', 'Factory Admin'
        DEPOT_ADMIN = 'DEPOT_ADMIN', 'Depot Admin'
        PENDING = 'PENDING', 'Pending role assignment'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PENDING)
    custom_role = models.ForeignKey('RoleDefinition', on_delete=models.PROTECT, null=True, blank=True, related_name='profiles')
    assigned_locations = models.ManyToManyField(Location, blank=True, related_name='assigned_profiles')
    legacy_role = models.CharField(max_length=20, blank=True)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    designation = models.CharField(max_length=100, default="IT Officer")

    def __str__(self):
        return f"{self.user.username} ({self.role_label})"

    @property
    def role_label(self):
        return self.custom_role.name if self.custom_role_id else self.get_role_display()


class RoleDefinition(TimeStampedModel):
    BASE_CHOICES = [
        (role.value, role.label) for role in (
            UserProfile.Role.HO_ADMIN, UserProfile.Role.FACTORY_ADMIN, UserProfile.Role.DEPOT_ADMIN,
        )
    ]

    name = models.CharField(max_length=80)
    base_role = models.CharField(max_length=20, choices=BASE_CHOICES)
    description = models.TextField(max_length=500, blank=True)

    class Meta:
        ordering = [Lower('name'), 'pk']
        constraints = [
            models.UniqueConstraint(Lower('name'), name='unique_role_name_casefold'),
        ]

    def __str__(self):
        return self.name


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, raw, **kwargs):
    if created and not raw:
        role = UserProfile.Role.SUPER_ADMIN if instance.is_superuser else UserProfile.Role.PENDING
        UserProfile.objects.create(user=instance, role=role)


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
