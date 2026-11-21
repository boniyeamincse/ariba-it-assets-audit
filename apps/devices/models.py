from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from apps.common.preferences import preferences
from apps.devices.configuration import (
    TAG_CATEGORY_CHOICES, add_months, format_asset_tag, normalize_asset_tag, suggest_tag_category,
)
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
    name = models.CharField(max_length=120)
    tag_category_code = models.CharField(max_length=4, choices=TAG_CATEGORY_CHOICES, blank=True)
    order = models.PositiveIntegerField(default=1)
    is_count_only = models.BooleanField(default=False, help_text="False for individual asset tracking")
    remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['category__order', 'order', 'name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self._state.adding and not self.tag_category_code:
            self.tag_category_code = suggest_tag_category(self.name)
        if self.tag_category_code not in dict(TAG_CATEGORY_CHOICES):
            raise ValidationError({'tag_category_code': 'Select a valid tag category code.'})
        if not self._state.adding:
            previous = DeviceType.objects.select_for_update().filter(pk=self.pk).values_list('tag_category_code', flat=True).first()
            if previous != self.tag_category_code and self.assets.exists():
                raise ValidationError({'tag_category_code': 'The tag category code is locked after an asset tag is issued.'})
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category_code': self.category.code,
            'tag_category_code': self.tag_category_code,
            'category_name': self.category.name,
            'order': self.order
        }


class AssetIdSequence(models.Model):
    last_number = models.PositiveBigIntegerField(default=0)


class IssuedAssetTag(models.Model):
    tag = models.CharField(max_length=150, primary_key=True)


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

    asset_tag = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Asset Tag / ID")
    retired_at = models.DateTimeField(null=True, blank=True, db_index=True)
    device_type = models.ForeignKey(DeviceType, on_delete=models.PROTECT, related_name='assets', verbose_name="Device / Asset Type")
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, related_name='assets', verbose_name="Location")
    owning_company = models.ForeignKey('locations.Company', on_delete=models.PROTECT, null=True, blank=True, related_name='owned_assets')
    
    brand = models.CharField(max_length=100, blank=True, null=True, verbose_name="Brand / Manufacturer")
    model_name = models.CharField(max_length=120, blank=True, null=True, verbose_name="Model Name / No")
    serial_number = models.CharField(max_length=120, blank=True, null=True, verbose_name="Serial Number")
    
    # Logical / Virtual specific fields
    vendor = models.CharField(max_length=120, blank=True, null=True, verbose_name="Vendor / Publisher")
    version = models.CharField(max_length=100, blank=True, null=True, verbose_name="Version / Edition")
    license_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="License Key / Subscription ID")
    host_server = models.CharField(max_length=150, blank=True, null=True, verbose_name="Host Server / Cloud Cluster")

    # Software Compliance & Risk Identification
    COMPLIANCE_CHOICES = (
        ('GENUINE', 'Genuine / Officially Licensed'),
        ('CRACKED_PIRATED', 'Cracked / Pirated (Unlicensed - High Risk)'),
        ('UNLICENSED_EXPIRED', 'Unlicensed / Expired Trial'),
        ('FREE_OPEN_SOURCE', 'Free / Open Source (Approved)'),
        ('OEM_BUNDLED', 'OEM Bundled / Pre-installed'),
    )

    RISK_LEVEL_CHOICES = (
        ('LOW', 'Low Risk (Compliant / Open Source)'),
        ('MEDIUM', 'Medium Risk (Expired / Non-Critical)'),
        ('HIGH', 'High Risk (Pirated Application / EDR Detection)'),
        ('CRITICAL', 'Critical Risk (Cracked OS / Server / Production Threat)'),
    )

    REMEDIATION_CHOICES = (
        ('COMPLIANT', 'Compliant - No Action Needed'),
        ('PURCHASE_OFFICIAL', 'Procure Official License (Budget Required)'),
        ('REPLACE_WITH_OPEN_SOURCE', 'Replace with Free / Open Source Alternative'),
        ('REMOVE_IMMEDIATELY', 'Remove / Uninstall Immediately (Security Threat)'),
    )

    compliance_status = models.CharField(
        max_length=30,
        choices=COMPLIANCE_CHOICES,
        default='GENUINE',
        verbose_name="License Compliance Status",
        db_index=True
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='LOW',
        verbose_name="Risk Level",
        db_index=True
    )
    remediation_plan = models.CharField(
        max_length=35,
        choices=REMEDIATION_CHOICES,
        default='COMPLIANT',
        verbose_name="Remediation / Mitigation Plan"
    )
    seats_purchased = models.PositiveIntegerField(default=1, verbose_name="Total Seats / Licenses")
    seats_allocated = models.PositiveIntegerField(default=1, verbose_name="Allocated / Used Seats")

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

    @classmethod
    def reserve_generated_tag(cls, config, location, device_type, company_code):
        sequence = AssetIdSequence.objects.filter(pk=1)
        next_number = Greatest(F('last_number') + 1, Value(config['asset_id_start']))
        limit = 10 ** config['asset_id_length']
        category_code = None
        while True:
            # UPDATE takes the write lock before we read the allocated number.
            if not sequence.update(last_number=next_number):
                AssetIdSequence.objects.get_or_create(pk=1)
                sequence.update(last_number=next_number)
            number = sequence.values_list('last_number', flat=True).get()
            if number >= limit:
                raise ValidationError({'asset_tag': 'The asset tag sequence is exhausted. Increase the number length in System Settings.'})
            if config['asset_id_include_company'] and not config['asset_id_company_code']:
                if not any(char.isascii() and char.isalnum() for char in company_code):
                    raise ValidationError({'asset_tag': 'Set an alphanumeric short code for the issuing company.'})
            if category_code is None:
                category_code = DeviceType.objects.select_for_update().values_list('tag_category_code', flat=True).get(pk=device_type.pk) or 'OTHR'
            tag = format_asset_tag(
                config, number, company_code=company_code,
                location_code=location.code, tag_category_code=category_code,
            )
            if len(tag) > cls._meta.get_field('asset_tag').max_length:
                raise ValidationError({'asset_tag': 'The generated asset tag exceeds 50 characters. Review Asset ID Configuration.'})
            _, reserved = IssuedAssetTag.objects.get_or_create(pk=normalize_asset_tag(tag))
            if reserved and not cls.objects.filter(asset_tag__iexact=tag).exists():
                return tag

    def save(self, *args, **kwargs):
        config = preferences()
        if self._state.adding:
            location = self.location
            device_type = self.device_type
            if not self.owning_company_id:
                self.owning_company = location.company
            company_code = self.owning_company.short_code
        with transaction.atomic():
            previous = None
            if self._state.adding:
                if not self.currency:
                    self.currency = config['asset_currency']
                if self.purchase_date and not self.warranty_expiry and config['default_warranty_months']:
                    purchase_date = self._meta.get_field('purchase_date').to_python(self.purchase_date)
                    self.warranty_expiry = add_months(purchase_date, config['default_warranty_months'])
                tag = normalize_asset_tag(self.asset_tag or '')
                if not tag:
                    tag = self.reserve_generated_tag(config, location, device_type, company_code)
                else:
                    if len(tag) > self._meta.get_field('asset_tag').max_length or any(
                        char.isspace() or not char.isprintable() for char in tag
                    ):
                        raise ValidationError({'asset_tag': 'Use up to 50 characters without spaces or control characters.'})
                    # Use the same first-write lock as automatic registration without advancing the counter.
                    AssetIdSequence.objects.filter(pk=1).update(last_number=F('last_number'))
                    DeviceType.objects.select_for_update().only('pk').get(pk=self.device_type_id)
                    if Asset.objects.filter(asset_tag__iexact=tag).exists():
                        raise ValidationError({'asset_tag': 'This asset tag has already been issued.'})
                    _, reserved = IssuedAssetTag.objects.get_or_create(pk=tag)
                    if not reserved:
                        raise ValidationError({'asset_tag': 'This asset tag has already been issued.'})
                self.asset_tag = tag
            else:
                previous = Asset.objects.select_for_update().filter(pk=self.pk).values(
                    'asset_tag', 'assigned_user', 'location_id', 'retired_at',
                ).first()
                if previous and self.asset_tag != previous['asset_tag']:
                    raise ValidationError({'asset_tag': 'An issued asset tag cannot be changed.'})
                if previous and previous['retired_at'] and (
                    self.retired_at != previous['retired_at'] or self.status != 'SCRAP' or self.is_active
                ):
                    raise ValidationError({'asset_tag': 'A retired asset cannot be reactivated.'})
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
            'owning_company': self.owning_company.name if self.owning_company_id else '',
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
            'compliance_status': self.compliance_status,
            'compliance_status_display': self.get_compliance_status_display(),
            'risk_level': self.risk_level,
            'risk_level_display': self.get_risk_level_display(),
            'remediation_plan': self.remediation_plan,
            'remediation_plan_display': self.get_remediation_plan_display(),
            'seats_purchased': self.seats_purchased,
            'seats_allocated': self.seats_allocated,
        }


class PendingAssetNotice(models.Model):
    subject = models.CharField(max_length=150)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
