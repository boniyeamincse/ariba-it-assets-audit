from django.db import models
from apps.common.models import TimeStampedModel
from apps.locations.models import Location
from apps.devices.models import DeviceType

class AuditSession(TimeStampedModel):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft / In-Progress'),
        ('SUBMITTED', 'Submitted for Verification'),
        ('VERIFIED', 'Verified by Location In-Charge'),
        ('APPROVED', 'Approved by Management / Sir'),
    )

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='audit_sessions')
    audit_date = models.DateField(db_index=True)
    auditor_name = models.CharField(max_length=120, default="IT Audit Team")
    verified_by_name = models.CharField(max_length=120, blank=True, null=True)
    approved_by_name = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-audit_date', '-created_at']
        unique_together = ('location', 'audit_date')

    def __str__(self):
        return f"{self.location.name} - Audit on {self.audit_date} [{self.get_status_display()}]"

    @property
    def total_qty(self):
        return sum(item.total_qty for item in self.items.all())

    @property
    def total_active(self):
        return sum(item.active_qty for item in self.items.all())

    @property
    def total_backup(self):
        return sum(item.backup_qty for item in self.items.all())

    @property
    def total_faulty(self):
        return sum(item.faulty_qty for item in self.items.all())

    @property
    def total_infrastructure(self):
        return sum(item.total_qty for item in self.items.filter(device_type__category__code='INFRASTRUCTURE'))

    @property
    def total_users(self):
        return sum(item.total_qty for item in self.items.filter(device_type__category__code='USERS'))

class AuditItem(TimeStampedModel):
    audit_session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name='items')
    device_type = models.ForeignKey(DeviceType, on_delete=models.CASCADE, related_name='audit_items')
    active_qty = models.PositiveIntegerField(default=0, help_text="Working / In-Use")
    backup_qty = models.PositiveIntegerField(default=0, help_text="Backup / Spare")
    faulty_qty = models.PositiveIntegerField(default=0, help_text="Faulty / Damaged")
    total_qty = models.PositiveIntegerField(default=0)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['device_type__category__order', 'device_type__order', 'device_type__name']
        unique_together = ('audit_session', 'device_type')

    def save(self, *args, **kwargs):
        # Auto calculate total quantity on save
        self.total_qty = self.active_qty + self.backup_qty + self.faulty_qty
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.device_type.name}: {self.total_qty} (Session: {self.audit_session.id})"

