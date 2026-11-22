from datetime import date
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.common.models import TimeStampedModel


class Vendor(TimeStampedModel):
    """
    Master registry of IT vendors, suppliers, OEMs, software publishers,
    and service contractors across Akij Group.
    """
    CATEGORY_CHOICES = (
        ('HARDWARE_OEM', 'Hardware OEM / Manufacturer'),
        ('SOFTWARE_PUBLISHER', 'Software Publisher / SaaS Provider'),
        ('SYSTEM_INTEGRATOR', 'System Integrator / Solution Partner'),
        ('AMC_PROVIDER', 'AMC / Maintenance Contractor'),
        ('ISP_TELECOM', 'ISP / Telecom Service Provider'),
        ('CLOUD_HOSTING', 'Cloud & Hosting Infrastructure'),
        ('GENERAL_SUPPLIER', 'IT Accessories & Consumables'),
    )

    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('PREFERRED', 'Preferred Partner'),
        ('UNDER_REVIEW', 'Under Review'),
        ('BLACKLISTED', 'Blacklisted'),
        ('INACTIVE', 'Inactive'),
    )

    vendor_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        db_index=True,
        verbose_name="Vendor Code",
        help_text="Unique identifier e.g. VND-2026-0001"
    )
    name = models.CharField(max_length=180, db_index=True, verbose_name="Vendor / Company Name")
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='GENERAL_SUPPLIER',
        verbose_name="Category"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        verbose_name="Status"
    )

    # Corporate & Tax Identification
    bin_tin_number = models.CharField(max_length=60, blank=True, null=True, verbose_name="BIN / TIN Number")
    trade_license_no = models.CharField(max_length=100, blank=True, null=True, verbose_name="Trade License No")
    vat_registration_no = models.CharField(max_length=100, blank=True, null=True, verbose_name="VAT Registration No")

    # Contact & Online Presence
    website = models.URLField(blank=True, null=True, verbose_name="Website")
    support_portal_url = models.URLField(blank=True, null=True, verbose_name="Support Portal / Helpdesk URL")
    helpline_number = models.CharField(max_length=60, blank=True, null=True, verbose_name="Helpdesk / Hotline")
    email = models.EmailField(blank=True, null=True, verbose_name="Official Email")
    phone = models.CharField(max_length=60, blank=True, null=True, verbose_name="Phone Number")
    address = models.TextField(blank=True, null=True, verbose_name="Office Address")
    city = models.CharField(max_length=100, blank=True, null=True, default="Dhaka", verbose_name="City")
    country = models.CharField(max_length=100, default="Bangladesh", verbose_name="Country")

    # Commercial & Credit Terms
    credit_period_days = models.PositiveIntegerField(
        default=30,
        verbose_name="Credit Period (Days)",
        help_text="Standard payment terms in days"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Internal Remarks")
    overall_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Overall Rating (out of 5)"
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"

    def __str__(self):
        return f"{self.name} ({self.vendor_code or self.get_category_display()})"

    def save(self, *args, **kwargs):
        if not self.vendor_code:
            current_year = timezone.now().year
            prefix = f"VND-{current_year}-"
            last_vendor = Vendor.objects.filter(vendor_code__startswith=prefix).order_by('-vendor_code').first()
            if last_vendor and last_vendor.vendor_code:
                try:
                    last_seq = int(last_vendor.vendor_code.split('-')[-1])
                    seq = last_seq + 1
                except (ValueError, IndexError):
                    seq = Vendor.objects.count() + 1
            else:
                seq = 1
            self.vendor_code = f"{prefix}{seq:04d}"
        super().save(*args, **kwargs)

    def recalculate_rating(self):
        evals = self.evaluations.all()
        if evals.exists():
            total = sum(e.composite_score for e in evals)
            self.overall_rating = round(Decimal(total) / Decimal(evals.count()), 2)
        else:
            self.overall_rating = Decimal('0.00')
        self.save(update_fields=['overall_rating'])


class VendorContact(TimeStampedModel):
    """
    Key personnel and escalation directory for a vendor.
    """
    CONTACT_TYPES = (
        ('PRIMARY', 'Primary Contact'),
        ('SALES', 'Sales & Account Manager'),
        ('TECHNICAL_SUPPORT', 'Technical Support / Service Engineer'),
        ('ESCALATION', 'Escalation Manager'),
        ('BILLING', 'Billing & Accounts'),
    )

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=120, verbose_name="Contact Name")
    designation = models.CharField(max_length=120, blank=True, null=True, verbose_name="Designation")
    contact_type = models.CharField(
        max_length=30,
        choices=CONTACT_TYPES,
        default='TECHNICAL_SUPPORT',
        verbose_name="Contact Role"
    )
    email = models.EmailField(blank=True, null=True, verbose_name="Email Address")
    phone = models.CharField(max_length=60, blank=True, null=True, verbose_name="Office Phone")
    mobile = models.CharField(max_length=60, blank=True, null=True, verbose_name="Mobile Number")
    is_primary = models.BooleanField(default=False, verbose_name="Primary Contact")

    class Meta:
        ordering = ['-is_primary', 'name']
        verbose_name = "Vendor Contact"
        verbose_name_plural = "Vendor Contacts"

    def __str__(self):
        return f"{self.name} - {self.get_contact_type_display()} ({self.vendor.name})"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Demote any other primary contacts for this vendor
            VendorContact.objects.filter(vendor=self.vendor, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class VendorContract(TimeStampedModel):
    """
    Contracts, AMCs, SLAs, and maintenance agreements associated with vendors.
    """
    CONTRACT_TYPE_CHOICES = (
        ('AMC_COMPREHENSIVE', 'AMC - Comprehensive (Parts & Service)'),
        ('AMC_NON_COMPREHENSIVE', 'AMC - Non-Comprehensive (Service Only)'),
        ('SLA', 'Service Level Agreement (SLA)'),
        ('SOFTWARE_LICENSE', 'Software Subscription / License Agreement'),
        ('HARDWARE_WARRANTY', 'Extended Hardware Warranty'),
        ('LEASING', 'Equipment Leasing Agreement'),
        ('ISP_INTERNET', 'Bandwidth & Internet Lease'),
    )

    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('EXPIRING_SOON', 'Expiring Soon'),
        ('EXPIRED', 'Expired'),
        ('TERMINATED', 'Terminated'),
    )

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='contracts')
    contract_number = models.CharField(
        max_length=80,
        unique=True,
        verbose_name="Contract / Agreement Number",
        help_text="e.g. AMC-2026-DEL-01"
    )
    title = models.CharField(max_length=200, verbose_name="Agreement Title")
    contract_type = models.CharField(
        max_length=35,
        choices=CONTRACT_TYPE_CHOICES,
        default='AMC_COMPREHENSIVE',
        verbose_name="Contract Type"
    )
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(verbose_name="Expiry / End Date")
    contract_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Contract Value"
    )
    currency = models.CharField(max_length=10, default='BDT', verbose_name="Currency")
    payment_terms = models.CharField(max_length=200, blank=True, null=True, verbose_name="Payment Schedule / Terms")
    sla_terms = models.TextField(
        blank=True,
        null=True,
        verbose_name="SLA Terms",
        help_text="e.g. 4-hour on-site response time, 99.9% uptime requirement"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        verbose_name="Status"
    )
    auto_renew = models.BooleanField(default=False, verbose_name="Auto-Renewing")
    document = models.FileField(upload_to='vendor_contracts/', blank=True, null=True, verbose_name="Signed Agreement PDF")
    covered_assets = models.ManyToManyField(
        'devices.Asset',
        blank=True,
        related_name='covered_contracts',
        verbose_name="Covered Assets / Hardware"
    )

    class Meta:
        ordering = ['end_date', 'title']
        verbose_name = "Vendor Contract / AMC"
        verbose_name_plural = "Vendor Contracts & AMCs"

    def __str__(self):
        return f"{self.contract_number} - {self.title} ({self.vendor.name})"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be prior to start date.'})

    @property
    def days_until_expiry(self):
        if not self.end_date:
            return 0
        today = timezone.localdate() if hasattr(timezone, 'localdate') else date.today()
        return (self.end_date - today).days

    @property
    def is_expired(self):
        return self.days_until_expiry < 0

    @property
    def urgency_level(self):
        days = self.days_until_expiry
        if days < 0:
            return 'expired'
        elif days <= 15:
            return 'critical'
        elif days <= 60:
            return 'warning'
        return 'safe'

    @property
    def expiry_display_text(self):
        days = self.days_until_expiry
        if days < 0:
            return f"Expired ({abs(days)} days ago)"
        elif days == 0:
            return "Expires today"
        elif days == 1:
            return "1 day left"
        elif days <= 30:
            return f"{days} days left"
        return f"{days} days remaining"


class VendorRMA(TimeStampedModel):
    """
    Tracks Return Merchandise Authorizations (RMA), warranty claims,
    and external repair cycles with vendors.
    """
    RMA_STATUS_CHOICES = (
        ('LOGGED', 'Logged / Prepared'),
        ('DISPATCHED', 'Dispatched to Vendor'),
        ('UNDER_DIAGNOSIS', 'Under Diagnosis / Repair'),
        ('REPAIRED', 'Repaired - Ready for Delivery'),
        ('REPLACED', 'Replaced with New Unit'),
        ('RETURNED', 'Returned & Verified at Site'),
        ('CLOSED', 'Closed'),
    )

    rma_number = models.CharField(
        max_length=80,
        unique=True,
        blank=True,
        verbose_name="RMA / Claim Number",
        help_text="e.g. RMA-2026-0001"
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='rma_claims', verbose_name="Vendor")
    asset = models.ForeignKey('devices.Asset', on_delete=models.PROTECT, related_name='rma_records', verbose_name="Asset")
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, related_name='rma_records', verbose_name="Location")
    issue_description = models.TextField(verbose_name="Reported Fault / Problem Description")
    dispatch_date = models.DateField(default=date.today, verbose_name="Dispatch Date")
    expected_return_date = models.DateField(blank=True, null=True, verbose_name="Expected Return Date")
    actual_return_date = models.DateField(blank=True, null=True, verbose_name="Actual Return Date")
    status = models.CharField(
        max_length=25,
        choices=RMA_STATUS_CHOICES,
        default='LOGGED',
        db_index=True,
        verbose_name="Claim Status"
    )
    standby_provided = models.BooleanField(
        default=False,
        verbose_name="Standby / Loaner Unit Provided"
    )
    replacement_serial_no = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name="Replacement Serial No (if replaced)"
    )
    repair_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
        null=True,
        verbose_name="Repair Cost (BDT)"
    )
    challan_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Challan / Gate Pass Reference"
    )
    resolution_notes = models.TextField(blank=True, null=True, verbose_name="Resolution Details")
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logged_rma_claims',
        verbose_name="Logged By"
    )

    class Meta:
        ordering = ['-dispatch_date', '-created_at']
        verbose_name = "Vendor RMA / Warranty Claim"
        verbose_name_plural = "Vendor RMA & Warranty Claims"

    def __str__(self):
        return f"{self.rma_number or 'Draft'} - {self.asset.asset_tag or self.asset.model_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.rma_number:
            current_year = timezone.now().year
            prefix = f"RMA-{current_year}-"
            last_rma = VendorRMA.objects.filter(rma_number__startswith=prefix).order_by('-rma_number').first()
            if last_rma and last_rma.rma_number:
                try:
                    last_seq = int(last_rma.rma_number.split('-')[-1])
                    seq = last_seq + 1
                except (ValueError, IndexError):
                    seq = VendorRMA.objects.count() + 1
            else:
                seq = 1
            self.rma_number = f"{prefix}{seq:04d}"
        super().save(*args, **kwargs)


class VendorEvaluation(TimeStampedModel):
    """
    Performance reviews, scorecard ratings, and feedback for suppliers.
    """
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='evaluations', verbose_name="Vendor")
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendor_evaluations',
        verbose_name="Evaluator"
    )
    review_period = models.CharField(max_length=60, default="Annual Review 2026", verbose_name="Review Period")
    delivery_score = models.PositiveSmallIntegerField(
        default=4,
        verbose_name="Delivery & SLA Adherence (1-5)",
        help_text="1: Very Poor, 5: Excellent"
    )
    quality_score = models.PositiveSmallIntegerField(
        default=4,
        verbose_name="Product Quality / Reliability (1-5)"
    )
    support_score = models.PositiveSmallIntegerField(
        default=4,
        verbose_name="Support Responsiveness & Turnaround (1-5)"
    )
    pricing_score = models.PositiveSmallIntegerField(
        default=4,
        verbose_name="Pricing & Commercial Terms (1-5)"
    )
    composite_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('4.00'),
        verbose_name="Weighted Composite Score"
    )
    comments = models.TextField(blank=True, null=True, verbose_name="Evaluation Remarks")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vendor Evaluation"
        verbose_name_plural = "Vendor Evaluations"

    def __str__(self):
        return f"{self.vendor.name} - {self.review_period} ({self.composite_score}/5.00)"

    def save(self, *args, **kwargs):
        # Weighted calculation: Delivery (30%), Quality (25%), Support (25%), Pricing (20%)
        weighted = (
            (Decimal(self.delivery_score) * Decimal('0.30')) +
            (Decimal(self.quality_score) * Decimal('0.25')) +
            (Decimal(self.support_score) * Decimal('0.25')) +
            (Decimal(self.pricing_score) * Decimal('0.20'))
        )
        self.composite_score = round(weighted, 2)
        super().save(*args, **kwargs)
        self.vendor.recalculate_rating()


class VendorDocument(TimeStampedModel):
    """
    Corporate compliance files, trade licenses, partner authorizations, and NDAs.
    """
    DOC_TYPES = (
        ('TRADE_LICENSE', 'Trade License'),
        ('TAX_CERTIFICATE', 'BIN / TIN / Tax Certificate'),
        ('PARTNERSHIP_CERT', 'Authorized Partner / Dealership Certificate'),
        ('SLA_DOCUMENT', 'SLA / Contract Agreement'),
        ('NDA', 'Non-Disclosure Agreement (NDA)'),
        ('OTHER', 'Other Supporting Document'),
    )

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='documents', verbose_name="Vendor")
    title = models.CharField(max_length=150, verbose_name="Document Title")
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES, default='OTHER', verbose_name="Document Type")
    file = models.FileField(upload_to='vendor_documents/', verbose_name="File Attachment")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Vendor Document"
        verbose_name_plural = "Vendor Documents"

    def __str__(self):
        return f"{self.title} ({self.get_doc_type_display()}) - {self.vendor.name}"
