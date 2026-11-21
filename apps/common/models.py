from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SystemSettings(models.Model):
    session_minutes = models.PositiveSmallIntegerField(
        default=480, validators=[MinValueValidator(15), MaxValueValidator(1440)]
    )
    activity_page_size = models.PositiveSmallIntegerField(
        default=25, validators=[MinValueValidator(10), MaxValueValidator(100)]
    )
    user_page_size = models.PositiveSmallIntegerField(
        default=25, validators=[MinValueValidator(10), MaxValueValidator(100)]
    )
    support_email = models.EmailField(blank=True)
    options = models.JSONField(default=dict, blank=True)

    @classmethod
    def current(cls):
        return cls.objects.filter(pk=1).first() or cls(pk=1)

class TimeStampedModel(models.Model):
    """
    Abstract base model that provides self-updating
    created_at, updated_at fields and active status.
    Ensures future-proof auditability across all models.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class SystemActivityLog(TimeStampedModel):
    """
    Tracks actions performed across the system (audit submissions, approvals, edits)
    for enterprise security and future compliance.
    """
    user_name = models.CharField(max_length=150, default="System")
    action = models.CharField(max_length=100) # e.g. 'CREATED_AUDIT', 'UPDATED_AUDIT', 'APPROVED'
    module = models.CharField(max_length=50) # 'Audits', 'Locations', 'Devices'
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.user_name} - {self.action}"
