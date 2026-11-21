from django.db import models
from django.utils import timezone
from apps.common.models import TimeStampedModel


class DomainRecord(TimeStampedModel):
    CATEGORY_CHOICES = (
        ('CORPORATE_PRIMARY', 'Corporate Primary (Group Root)'),
        ('BUSINESS_UNIT', 'Business Unit / Sister Concern'),
        ('NATIONAL_CCTLD', 'National ccTLD (.com.bd / .bd)'),
        ('ECOMMERCE', 'E-Commerce & Digital Store'),
        ('ERP_PORTAL', 'ERP / Subdomains / Internal Portals'),
        ('PARKED_DEFENSIVE', 'Parked / Brand Defensive'),
    )

    REGISTRAR_CHOICES = (
        ('GODADDY', 'GoDaddy'),
        ('NAMECHEAP', 'Namecheap'),
        ('BTCL', 'BTCL (.bd Domains)'),
        ('CLOUDFLARE', 'Cloudflare Registrar'),
        ('AWS_ROUTE53', 'AWS Route 53'),
        ('HOSTINGER', 'Hostinger'),
        ('NETWORK_SOLUTIONS', 'Network Solutions'),
        ('OTHER', 'Other Registrar'),
    )

    DNS_PROVIDER_CHOICES = (
        ('CLOUDFLARE', 'Cloudflare DNS (Proxy & WAF)'),
        ('AWS_ROUTE53', 'AWS Route 53'),
        ('CPANEL', 'cPanel / DirectAdmin Server'),
        ('BTCL_DNS', 'BTCL Nameservers'),
        ('REGISTRAR_DEFAULT', 'Registrar Default Nameservers'),
        ('OTHER', 'Other DNS Provider'),
    )

    MAIL_PROVIDER_CHOICES = (
        ('MICROSOFT_365', 'Microsoft 365 (Exchange Online)'),
        ('GOOGLE_WORKSPACE', 'Google Workspace (Gmail)'),
        ('ZIMBRA', 'Zimbra On-Premises Mail Server'),
        ('ZOHO', 'Zoho Workplace'),
        ('CPANEL_MAIL', 'cPanel Webmail'),
        ('NONE', 'None / No Mail Routing'),
    )

    SSL_STATUS_CHOICES = (
        ('ACTIVE', 'SSL Active & Secure'),
        ('EXPIRING_SOON', 'SSL Expiring Soon (< 30 Days)'),
        ('EXPIRED', 'SSL Expired (Security Threat)'),
        ('NOT_CONFIGURED', 'Not Configured (HTTP Only)'),
    )

    STATUS_CHOICES = (
        ('ACTIVE', 'Active / Production'),
        ('EXPIRING_SOON', 'Expiring Soon (< 30 Days)'),
        ('EXPIRED', 'Expired / Action Required'),
        ('PARKED', 'Parked / Idle'),
        ('REDIRECTED', 'Redirected (301 Forwarding)'),
    )

    # 1. Domain Identity & Ownership
    domain_name = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name="Domain Name (FQDN)",
        help_text="e.g. akijplastics.com"
    )
    company = models.ForeignKey(
        'locations.Company',
        on_delete=models.PROTECT,
        related_name='domain_records',
        verbose_name="Owning Company / SBU"
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='BUSINESS_UNIT',
        db_index=True,
        verbose_name="Domain Classification"
    )

    # 2. Registrar & Billing Details
    registrar = models.CharField(
        max_length=50,
        choices=REGISTRAR_CHOICES,
        default='GODADDY',
        verbose_name="Domain Registrar",
        db_index=True
    )
    registrar_account_email = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Registrar Account / Owner Email"
    )
    invoice_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Latest Invoice / PO Number"
    )
    annual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Annual Renewal Cost"
    )
    currency = models.CharField(
        max_length=10,
        default="USD",
        verbose_name="Currency"
    )

    # 3. Registration Lifecycle & Expiry
    registration_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Initial Registration Date"
    )
    expiry_date = models.DateField(
        db_index=True,
        verbose_name="Domain Expiry Date"
    )
    auto_renewal = models.BooleanField(
        default=True,
        verbose_name="Auto-Renewal Enabled"
    )

    # 4. DNS & Network Infrastructure
    dns_provider = models.CharField(
        max_length=50,
        choices=DNS_PROVIDER_CHOICES,
        default='CLOUDFLARE',
        verbose_name="DNS Management Provider"
    )
    primary_nameserver = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Primary Nameserver (NS1)"
    )
    secondary_nameserver = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Secondary Nameserver (NS2)"
    )
    primary_a_record_ip = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name="Hosting / Target Web Server IP"
    )
    hosting_provider = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name="Hosting Provider / Server Host"
    )
    mail_provider = models.CharField(
        max_length=40,
        choices=MAIL_PROVIDER_CHOICES,
        default='MICROSOFT_365',
        verbose_name="Corporate Mail Provider"
    )

    # 5. SSL / TLS Certificate Lifecycle
    ssl_status = models.CharField(
        max_length=30,
        choices=SSL_STATUS_CHOICES,
        default='ACTIVE',
        verbose_name="SSL Certificate Status"
    )
    ssl_provider = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="SSL Issuer / Certificate Authority"
    )
    ssl_expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="SSL Certificate Expiry Date"
    )

    # 6. Operational Status & IT Custody
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True,
        verbose_name="Domain Operational Status"
    )
    technical_contact = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="In-Charge IT Executive / Admin"
    )
    remarks = models.TextField(
        blank=True,
        null=True,
        verbose_name="Remarks / Renewal Notes"
    )

    class Meta:
        ordering = ['expiry_date', 'domain_name']
        verbose_name = "Domain Record"
        verbose_name_plural = "Domain Records"

    def __str__(self):
        comp = getattr(self.company, 'short_code', '') or getattr(self.company, 'name', '')
        return f"{self.domain_name} ({comp})"

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return 9999
        today = timezone.now().date()
        return (self.expiry_date - today).days

    @property
    def is_expired(self):
        return self.days_until_expiry < 0

    @property
    def is_expiring_soon(self):
        return 0 <= self.days_until_expiry <= 30

    @property
    def abs_days_until_expiry(self):
        return abs(self.days_until_expiry)

    @property
    def days_until_ssl_expiry(self):
        if not self.ssl_expiry_date:
            return None
        today = timezone.now().date()
        return (self.ssl_expiry_date - today).days

    @property
    def abs_days_until_ssl_expiry(self):
        days = self.days_until_ssl_expiry
        return abs(days) if days is not None else None

    @property
    def is_ssl_expired(self):
        days = self.days_until_ssl_expiry
        return days is not None and days < 0

    @property
    def is_ssl_expiring_soon(self):
        days = self.days_until_ssl_expiry
        return days is not None and 0 <= days <= 30

    def clean(self):
        # Auto-compute operational status based on expiry date
        if self.domain_name:
            domain = self.domain_name.strip().lower()
            if domain.startswith('http://') or domain.startswith('https://'):
                domain = domain.split('://', 1)[1]
            domain = domain.split('/', 1)[0]
            self.domain_name = domain
        days = self.days_until_expiry
        if days < 0 and self.status != 'PARKED':
            self.status = 'EXPIRED'
        elif 0 <= days <= 30 and self.status not in ('PARKED', 'REDIRECTED'):
            self.status = 'EXPIRING_SOON'
        elif days > 30 and self.status in ('EXPIRED', 'EXPIRING_SOON'):
            self.status = 'ACTIVE'

        # Auto-compute SSL status if date is provided
        ssl_days = self.days_until_ssl_expiry
        if ssl_days is not None:
            if ssl_days < 0:
                self.ssl_status = 'EXPIRED'
            elif 0 <= ssl_days <= 30:
                self.ssl_status = 'EXPIRING_SOON'
            else:
                self.ssl_status = 'ACTIVE'

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def to_dict(self):
        return {
            'id': self.id,
            'domain_name': self.domain_name,
            'company': self.company.name if self.company else '',
            'company_short_code': self.company.short_code if self.company else '',
            'category': self.get_category_display(),
            'registrar': self.get_registrar_display(),
            'registrar_code': self.registrar,
            'registrar_account_email': self.registrar_account_email or '',
            'invoice_number': self.invoice_number or '',
            'annual_cost': float(self.annual_cost),
            'currency': self.currency,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'auto_renewal': self.auto_renewal,
            'days_until_expiry': self.days_until_expiry,
            'is_expired': self.is_expired,
            'is_expiring_soon': self.is_expiring_soon,
            'dns_provider': self.get_dns_provider_display(),
            'primary_nameserver': self.primary_nameserver or '',
            'secondary_nameserver': self.secondary_nameserver or '',
            'primary_a_record_ip': self.primary_a_record_ip or '',
            'hosting_provider': self.hosting_provider or '',
            'mail_provider': self.get_mail_provider_display(),
            'ssl_status': self.ssl_status,
            'ssl_status_display': self.get_ssl_status_display(),
            'ssl_provider': self.ssl_provider or '',
            'ssl_expiry_date': self.ssl_expiry_date.isoformat() if self.ssl_expiry_date else None,
            'days_until_ssl_expiry': self.days_until_ssl_expiry,
            'status': self.status,
            'status_display': self.get_status_display(),
            'technical_contact': self.technical_contact or '',
            'remarks': self.remarks or '',
        }
