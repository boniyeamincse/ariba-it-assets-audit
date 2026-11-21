from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.locations.models import Company
from apps.domains.models import DomainRecord


class Command(BaseCommand):
    help = "Seed corporate domain records for Akij Group SBUs and subsidiaries."

    def handle(self, *args, **options):
        today = timezone.now().date()

        akij_group = Company.objects.filter(name__icontains='Akij Group').first()
        plastics = Company.objects.filter(name__icontains='Plastics').first()
        ceramics = Company.objects.filter(name__icontains='Ceramics').first() or Company.objects.first()
        jute = Company.objects.filter(name__icontains='Jute').first() or Company.objects.first()

        if not akij_group:
            akij_group = Company.objects.first()
        if not plastics:
            plastics = akij_group

        sample_domains = [
            {
                'domain_name': 'akij.net',
                'company': akij_group,
                'category': 'CORPORATE_PRIMARY',
                'registrar': 'GODADDY',
                'registrar_account_email': 'noc@akij.net',
                'invoice_number': 'INV-GD-2024-9120',
                'annual_cost': 24.99,
                'currency': 'USD',
                'registration_date': today - timedelta(days=3650),
                'expiry_date': today + timedelta(days=280),
                'auto_renewal': True,
                'dns_provider': 'CLOUDFLARE',
                'primary_nameserver': 'bella.ns.cloudflare.com',
                'secondary_nameserver': 'wade.ns.cloudflare.com',
                'primary_a_record_ip': '104.21.54.12',
                'hosting_provider': 'Cloudflare Edge / AWS',
                'mail_provider': 'MICROSOFT_365',
                'ssl_status': 'ACTIVE',
                'ssl_provider': 'Cloudflare Universal SSL',
                'ssl_expiry_date': today + timedelta(days=120),
                'status': 'ACTIVE',
                'technical_contact': 'Md. Aminur Rahman (aminur@akij.net)',
                'remarks': 'Primary corporate identity domain for Akij Group. Microsoft 365 Exchange Online and SPF/DKIM/DMARC configured.',
            },
            {
                'domain_name': 'akijplastics.com',
                'company': plastics,
                'category': 'BUSINESS_UNIT',
                'registrar': 'GODADDY',
                'registrar_account_email': 'it.plastics@akij.net',
                'invoice_number': 'INV-GD-2023-4112',
                'annual_cost': 18.50,
                'currency': 'USD',
                'registration_date': today - timedelta(days=1825),
                'expiry_date': today + timedelta(days=22),  # Expiring soon (< 30 days)
                'auto_renewal': True,
                'dns_provider': 'CLOUDFLARE',
                'primary_nameserver': 'dina.ns.cloudflare.com',
                'secondary_nameserver': 'noah.ns.cloudflare.com',
                'primary_a_record_ip': '172.67.199.45',
                'hosting_provider': 'AWS EC2 Singapore',
                'mail_provider': 'MICROSOFT_365',
                'ssl_status': 'ACTIVE',
                'ssl_provider': "Let's Encrypt Authority X3",
                'ssl_expiry_date': today + timedelta(days=45),
                'status': 'ACTIVE',
                'technical_contact': 'NOC Team (it.plastics@akij.net)',
                'remarks': 'Official portal of Akij Plastics Ltd. Renewal notice received from GoDaddy.',
            },
            {
                'domain_name': 'akijcement.com',
                'company': ceramics,
                'category': 'BUSINESS_UNIT',
                'registrar': 'NAMECHEAP',
                'registrar_account_email': 'cement.it@akij.net',
                'invoice_number': 'NC-889123-2024',
                'annual_cost': 16.00,
                'currency': 'USD',
                'registration_date': today - timedelta(days=2190),
                'expiry_date': today + timedelta(days=195),
                'auto_renewal': True,
                'dns_provider': 'AWS_ROUTE53',
                'primary_nameserver': 'ns-112.awsdns-14.com',
                'secondary_nameserver': 'ns-844.awsdns-41.net',
                'primary_a_record_ip': '52.77.210.88',
                'hosting_provider': 'AWS Route 53 & S3 CloudFront',
                'mail_provider': 'GOOGLE_WORKSPACE',
                'ssl_status': 'ACTIVE',
                'ssl_provider': 'Amazon Trust Services (ACM)',
                'ssl_expiry_date': today + timedelta(days=210),
                'status': 'ACTIVE',
                'technical_contact': 'Lead Systems Engineer (cement.it@akij.net)',
                'remarks': 'Akij Cement website and product dealer portal.',
            },
            {
                'domain_name': 'akij.com.bd',
                'company': akij_group,
                'category': 'NATIONAL_CCTLD',
                'registrar': 'BTCL',
                'registrar_account_email': 'admin@akij.net',
                'invoice_number': 'BTCL-BD-2024-0041',
                'annual_cost': 1500.00,
                'currency': 'BDT',
                'registration_date': today - timedelta(days=5000),
                'expiry_date': today + timedelta(days=420),
                'auto_renewal': False,
                'dns_provider': 'BTCL_DNS',
                'primary_nameserver': 'ns1.btcl.com.bd',
                'secondary_nameserver': 'ns2.btcl.com.bd',
                'primary_a_record_ip': '103.14.22.10',
                'hosting_provider': 'National Data Center / BTCL DMZ',
                'mail_provider': 'MICROSOFT_365',
                'ssl_status': 'ACTIVE',
                'ssl_provider': 'Sectigo RSA Domain Validation',
                'ssl_expiry_date': today + timedelta(days=290),
                'status': 'ACTIVE',
                'technical_contact': 'Central IT Telecom Admin',
                'remarks': 'Bangladesh ccTLD reservation. BTCL physical bill processing required annually.',
            },
            {
                'domain_name': 'akijjute.com',
                'company': jute,
                'category': 'BUSINESS_UNIT',
                'registrar': 'GODADDY',
                'registrar_account_email': 'it@akijjute.com',
                'invoice_number': 'GD-JUTE-2023',
                'annual_cost': 21.00,
                'currency': 'USD',
                'registration_date': today - timedelta(days=1400),
                'expiry_date': today + timedelta(days=75),
                'auto_renewal': False,
                'dns_provider': 'CPANEL',
                'primary_nameserver': 'ns1.akijhost.com',
                'secondary_nameserver': 'ns2.akijhost.com',
                'primary_a_record_ip': '103.229.25.14',
                'hosting_provider': 'On-Premises Dedicated Server',
                'mail_provider': 'ZIMBRA',
                'ssl_status': 'EXPIRING_SOON',
                'ssl_provider': "Let's Encrypt (cPanel AutoSSL)",
                'ssl_expiry_date': today + timedelta(days=14),  # SSL expiring soon (< 30 days)
                'status': 'ACTIVE',
                'technical_contact': 'Jute IT Officer',
                'remarks': 'AutoSSL renewal job failing due to DNS rate limits. Requires manual review.',
            },
            {
                'domain_name': 'akijstore.com',
                'company': plastics,
                'category': 'ECOMMERCE',
                'registrar': 'CLOUDFLARE',
                'registrar_account_email': 'digital@akijplastics.com',
                'invoice_number': 'CF-INV-77291',
                'annual_cost': 9.15,
                'currency': 'USD',
                'registration_date': today - timedelta(days=730),
                'expiry_date': today - timedelta(days=12),  # Expired
                'auto_renewal': False,
                'dns_provider': 'CLOUDFLARE',
                'primary_nameserver': 'dns1.cloudflare.com',
                'secondary_nameserver': 'dns2.cloudflare.com',
                'primary_a_record_ip': '104.18.28.19',
                'hosting_provider': 'Vercel / Next.js Storefront',
                'mail_provider': 'MICROSOFT_365',
                'ssl_status': 'EXPIRED',
                'ssl_provider': 'Cloudflare Edge SSL',
                'ssl_expiry_date': today - timedelta(days=5),
                'status': 'EXPIRED',
                'technical_contact': 'E-Commerce IT Lead',
                'remarks': 'Expired test domain. Credit card charge failed at Cloudflare. Needs urgent renewal.',
            },
        ]

        created_count = 0
        updated_count = 0

        for item in sample_domains:
            name = item.pop('domain_name')
            obj, created = DomainRecord.objects.update_or_create(
                domain_name=name,
                defaults=item
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded domains: {created_count} created, {updated_count} updated."
            )
        )
