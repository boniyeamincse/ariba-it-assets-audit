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

    def to_dict(self):
        infra_items = []
        user_items = []
        for itm in self.items.select_related('device_type', 'device_type__category').all():
            data = itm.to_dict()
            if itm.device_type.category.code == 'INFRASTRUCTURE':
                infra_items.append(data)
            else:
                user_items.append(data)

        return {
            'id': self.id,
            'company': self.location.company.name,
            'location': self.location.name,
            'location_code': self.location.code,
            'location_type': self.location.get_location_type_display(),
            'auditDate': str(self.audit_date),
            'auditedBy': self.auditor_name,
            'verifiedBy': self.verified_by_name or '',
            'approvedBy': self.approved_by_name or '',
            'status': self.status,
            'status_display': self.get_status_display(),
            'remarks': self.remarks or '',
            'summary': {
                'totalDevices': self.total_qty,
                'totalActive': self.total_active,
                'totalBackup': self.total_backup,
                'totalFaulty': self.total_faulty,
                'infrastructureQty': self.total_infrastructure,
                'userDevicesQty': self.total_users
            },
            'infrastructure': infra_items,
            'users': user_items
        }


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

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_type.id,
            'device': self.device_type.name,
            'category': self.device_type.category.name,
            'category_code': self.device_type.category.code,
            'active': self.active_qty,
            'backup': self.backup_qty,
            'faulty': self.faulty_qty,
            'qty': self.total_qty,
            'remarks': self.remarks or ''
        }
