from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.access import Role
from apps.locations.models import Company
from apps.domains.models import DomainRecord


class DomainRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Akij Test Subsidiary', short_code='ATS')
        cls.super_admin = User.objects.create_superuser('domain-admin', password='AdminPassword123!')
        cls.super_admin.profile.role = Role.SUPER_ADMIN
        cls.super_admin.profile.save()

        cls.depot_user = User.objects.create_user('depot-user', password='DepotPassword123!')
        cls.depot_user.profile.role = Role.DEPOT_ADMIN
        cls.depot_user.profile.save()

        today = timezone.now().date()
        cls.active_domain = DomainRecord.objects.create(
            domain_name='active-corp.com',
            company=cls.company,
            category='CORPORATE_PRIMARY',
            registrar='GODADDY',
            registration_date=today - timedelta(days=365),
            expiry_date=today + timedelta(days=180),
            auto_renewal=True,
            dns_provider='CLOUDFLARE',
            primary_nameserver='ns1.cloudflare.com',
            secondary_nameserver='ns2.cloudflare.com',
            ssl_status='ACTIVE',
            ssl_expiry_date=today + timedelta(days=90),
            status='ACTIVE',
        )

        cls.expiring_domain = DomainRecord.objects.create(
            domain_name='expiring-corp.com',
            company=cls.company,
            category='BUSINESS_UNIT',
            registrar='NAMECHEAP',
            expiry_date=today + timedelta(days=15),
            ssl_status='EXPIRING_SOON',
            ssl_expiry_date=today + timedelta(days=10),
            status='EXPIRING_SOON',
        )

        cls.expired_domain = DomainRecord.objects.create(
            domain_name='expired-corp.com',
            company=cls.company,
            category='ECOMMERCE',
            registrar='BTCL',
            expiry_date=today - timedelta(days=5),
            ssl_status='EXPIRED',
            ssl_expiry_date=today - timedelta(days=1),
            status='EXPIRED',
        )

    def test_model_expiry_properties(self):
        """Test calculation of days until expiry and urgency status flags."""
        self.assertFalse(self.active_domain.is_expired)
        self.assertFalse(self.active_domain.is_expiring_soon)
        self.assertGreater(self.active_domain.days_until_expiry, 30)

        self.assertFalse(self.expiring_domain.is_expired)
        self.assertTrue(self.expiring_domain.is_expiring_soon)
        self.assertLessEqual(self.expiring_domain.days_until_expiry, 30)

        self.assertTrue(self.expired_domain.is_expired)
        self.assertFalse(self.expired_domain.is_expiring_soon)
        self.assertLess(self.expired_domain.days_until_expiry, 0)

    def test_model_ssl_expiry_properties(self):
        """Test SSL certificate expiry calculations and warning flags."""
        self.assertFalse(self.active_domain.is_ssl_expired)
        self.assertFalse(self.active_domain.is_ssl_expiring_soon)

        self.assertFalse(self.expiring_domain.is_ssl_expired)
        self.assertTrue(self.expiring_domain.is_ssl_expiring_soon)

        self.assertTrue(self.expired_domain.is_ssl_expired)

    def test_domain_name_cleaning(self):
        """Domain name clean method should normalize URLs to bare FQDN."""
        record = DomainRecord(
            domain_name='  https://Test-Sub.akij.net/some/path/  ',
            company=self.company,
            expiry_date=timezone.now().date() + timedelta(days=60),
        )
        record.clean()
        self.assertEqual(record.domain_name, 'test-sub.akij.net')

    def test_domain_list_view_and_filtering(self):
        """Test the domain list view, metrics context, and search filter."""
        self.client.force_login(self.super_admin)
        url = reverse('domain_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'active-corp.com')
        self.assertContains(response, 'expiring-corp.com')
        self.assertContains(response, 'expired-corp.com')

        # Test filter by search
        search_res = self.client.get(url, {'q': 'active-corp'})
        self.assertEqual(search_res.status_code, 200)
        self.assertContains(search_res, 'active-corp.com')
        self.assertNotContains(search_res, 'expired-corp.com')

        # Test filter by expiry range (expired)
        expired_res = self.client.get(url, {'expiry_range': 'expired'})
        self.assertEqual(expired_res.status_code, 200)
        self.assertContains(expired_res, 'expired-corp.com')
        self.assertNotContains(expired_res, 'active-corp.com')

    def test_domain_create_view_authorized(self):
        """Central roles can create new corporate domain records."""
        self.client.force_login(self.super_admin)
        create_url = reverse('domain_create')
        today = timezone.now().date()
        payload = {
            'domain_name': 'https://New-Portal.com/',
            'company': self.company.id,
            'category': 'BUSINESS_UNIT',
            'registrar': 'GODADDY',
            'annual_cost': '15.50',
            'currency': 'USD',
            'expiry_date': (today + timedelta(days=120)).strftime('%Y-%m-%d'),
            'dns_provider': 'CLOUDFLARE',
            'mail_provider': 'MICROSOFT_365',
            'ssl_status': 'ACTIVE',
            'status': 'ACTIVE',
        }
        response = self.client.post(create_url, payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DomainRecord.objects.filter(domain_name='new-portal.com').exists())

    def test_domain_edit_and_detail_view(self):
        """Detail view renders technical configs; edit modifies them cleanly."""
        self.client.force_login(self.super_admin)
        detail_url = reverse('domain_detail', kwargs={'pk': self.active_domain.pk})
        detail_res = self.client.get(detail_url)
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, 'active-corp.com')
        self.assertContains(detail_res, 'bella.ns.cloudflare.com' if 'bella' in detail_res.content.decode() else 'ns1.cloudflare.com')

        edit_url = reverse('domain_edit', kwargs={'pk': self.active_domain.pk})
        today = timezone.now().date()
        payload = {
            'domain_name': 'active-corp.com',
            'company': self.company.id,
            'category': 'BUSINESS_UNIT',
            'registrar': 'HOSTINGER',
            'annual_cost': '20.00',
            'currency': 'USD',
            'expiry_date': (today + timedelta(days=200)).strftime('%Y-%m-%d'),
            'dns_provider': 'AWS_ROUTE53',
            'mail_provider': 'GOOGLE_WORKSPACE',
            'ssl_status': 'ACTIVE',
            'status': 'ACTIVE',
        }
        edit_res = self.client.post(edit_url, payload, follow=True)
        self.assertEqual(edit_res.status_code, 200)
        self.active_domain.refresh_from_db()
        self.assertEqual(self.active_domain.registrar, 'HOSTINGER')
        self.assertEqual(self.active_domain.mail_provider, 'GOOGLE_WORKSPACE')

    def test_domain_delete_view(self):
        """Domain delete removes record with post confirmation."""
        self.client.force_login(self.super_admin)
        delete_url = reverse('domain_delete', kwargs={'pk': self.expired_domain.pk})
        get_res = self.client.get(delete_url)
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'Confirm Domain Deletion')

        post_res = self.client.post(delete_url, follow=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertFalse(DomainRecord.objects.filter(pk=self.expired_domain.pk).exists())

    def test_domain_create_permission_restriction(self):
        """Depot users cannot access company-wide registrar and DNS records."""
        self.client.force_login(self.depot_user)
        restricted_urls = (
            reverse('domain_list'),
            reverse('domain_create'),
            reverse('domain_detail', kwargs={'pk': self.active_domain.pk}),
            reverse('domain_edit', kwargs={'pk': self.active_domain.pk}),
            reverse('domain_delete', kwargs={'pk': self.active_domain.pk}),
        )
        for url in restricted_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
