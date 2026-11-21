from django.db import models, transaction
from apps.common.preferences import preferences
from apps.devices.configuration import add_months, asset_tag_components
from apps.devices.notifications import queue_asset_notifications
from apps.common.models import TimeStampedModel

class DeviceCategory(TimeStampedModel):
    CATEGORY_KEYS = (
        ('INFRASTRUCTURE', 'Infrastructure'),
        ('USERS', 'Users / End-User Devices'),
        ('LOGICAL', 'Software & Logical Assets'),
    )
    code = models.CharField(max_length=40, choices=CATEGORY_KEYS, unique=True)
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name_plural = "Device Categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class DeviceType(TimeStampedModel):
    category = models.ForeignKey(DeviceCategory, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=120) # e.g. 'Laptop', 'Core Switch', 'Laser Printer'
    order = models.PositiveIntegerField(default=1)
    is_count_only = models.BooleanField(default=False, help_text="False for individual asset tracking")
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['category__order', 'order', 'name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category_code': self.category.code,
            'category_name': self.category.name,
            'order': self.order
        }


class AssetIdSequence(models.Model):
    last_number = models.PositiveBigIntegerField(default=0)


class Asset(TimeStampedModel):
    """
    Physical and Logical IT asset tracked location-wise across Akij Group.
    """
    NATURE_CHOICES = (
        ('PHYSICAL', 'Physical (Hardware)'),
        ('LOGICAL', 'Logical / Virtual (Software/License/Cloud)'),
    )

    STATUS_CHOICES = (
        ('IN_USE', 'Working / In-Use'),
        ('BACKUP', 'Backup / Spare'),
        ('FAULTY', 'Faulty / Under Repair'),
        ('SCRAP', 'Damaged / Scrap'),
    )

    asset_nature = models.CharField(
        max_length=20,
        choices=NATURE_CHOICES,
        default='PHYSICAL',
        verbose_name="Asset Nature",
        db_index=True
    )

    asset_tag = models.CharField(max_length=50, unique=True, verbose_name="Asset Tag / ID", db_index=True)
    device_type = models.ForeignKey(DeviceType, on_delete=models.CASCADE, related_name='assets', verbose_name="Device / Asset Type")
    location = models.ForeignKey('locations.Location', on_delete=models.CASCADE, related_name='assets', verbose_name="Location")
    
    brand = models.CharField(max_length=100, blank=True, null=True, verbose_name="Brand / Manufacturer")
    model_name = models.CharField(max_length=120, blank=True, null=True, verbose_name="Model Name / No")
    serial_number = models.CharField(max_length=120, blank=True, null=True, verbose_name="Serial Number")
    
    # Logical / Virtual specific fields
    vendor = models.CharField(max_length=120, blank=True, null=True, verbose_name="Vendor / Publisher")
    version = models.CharField(max_length=100, blank=True, null=True, verbose_name="Version / Edition")
    license_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="License Key / Subscription ID")
    host_server = models.CharField(max_length=150, blank=True, null=True, verbose_name="Host Server / Cloud Cluster")

    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="Department")
    assigned_user = models.CharField(max_length=120, blank=True, null=True, verbose_name="Assigned User / Employee")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_USE', verbose_name="Status")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP Address")
    mac_address = models.CharField(max_length=50, blank=True, null=True, verbose_name="MAC Address")
    
    condition = models.CharField(max_length=60, blank=True)
    criticality = models.CharField(max_length=60, blank=True)
    ownership_type = models.CharField(max_length=60, blank=True)
    procurement_type = models.CharField(max_length=60, blank=True)
    currency = models.CharField(max_length=3, blank=True)

    purchase_date = models.DateField(blank=True, null=True, verbose_name="Purchase Date")
    warranty_expiry = models.DateField(blank=True, null=True, verbose_name="Warranty Expiry")
    remarks = models.TextField(blank=True, null=True, verbose_name="Remarks / Specifications")

    class Meta:
        ordering = ['location', '-created_at']

    @transaction.atomic
    def save(self, *args, **kwargs):
        config = preferences()
        previous = None
        if self._state.adding:
            if not self.currency:
                self.currency = config['asset_currency']
            if self.purchase_date and not self.warranty_expiry and config['default_warranty_months']:
                purchase_date = self._meta.get_field('purchase_date').to_python(self.purchase_date)
                self.warranty_expiry = add_months(purchase_date, config['default_warranty_months'])
        elif config.get('email_notifications'):
            previous = Asset.objects.filter(pk=self.pk).values('assigned_user', 'location_id').first()

        if not self.asset_tag:
            sequence, _ = AssetIdSequence.objects.select_for_update().get_or_create(pk=1)
            number = max(config['asset_id_start'], sequence.last_number + 1)
            parts = asset_tag_components(config, self.location, self.device_type.category, self.device_type)
            separator = config['asset_id_separator']
            length = config['asset_id_length']
            while True:
                candidate = separator.join([*parts, str(number).zfill(length)])
                if not Asset.objects.filter(asset_tag=candidate).exists():
                    break
                number += 1
            sequence.last_number = number
            sequence.save(update_fields=['last_number'])
            self.asset_tag = candidate
        super().save(*args, **kwargs)
        queue_asset_notifications(self, previous, config)

    def __str__(self):
        return f"[{self.asset_tag}] {self.device_type.name} - {self.location.name}"

    def to_dict(self):
        return {
            'id': self.id,
            'asset_tag': self.asset_tag,
            'asset_nature': self.asset_nature,
            'asset_nature_display': self.get_asset_nature_display(),
            'device_type': self.device_type.name,
            'category': self.device_type.category.name,
            'location_id': self.location.location_id,
            'location_name': self.location.name,
            'brand': self.brand or '',
            'model': self.model_name or '',
            'serial_number': self.serial_number or '',
            'department': self.department or '',
            'assigned_user': self.assigned_user or '',
            'status': self.get_status_display(),
            'status_code': self.status,
            'license_key': self.license_key or '',
            'version': self.version or '',
            'vendor': self.vendor or '',
            'host_server': self.host_server or '',
        }


class PendingAssetNotice(models.Model):
    subject = models.CharField(max_length=150)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
