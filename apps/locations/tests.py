from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.access import Role
from apps.audits.models import AuditItem, AuditSession
from apps.devices.models import Asset, DeviceCategory, DeviceType
from apps.locations.models import Company, Location


class LocationDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('location-admin')
        cls.company = Company.objects.create(name='Acme Group', short_code='ACME')
        cls.other_company = Company.objects.create(name='Regional Group', short_code='REGIONAL')
        cls.factory = Location.objects.create(name='Main factory', company=cls.company, code='MAIN', city='Dhaka')
        cls.subsite = Location.objects.create(
            name='Factory annex', company=cls.company, code='ANNEX', parent_location=cls.factory, is_active=False,
        )
        cls.other = Location.objects.create(name='Regional factory', company=cls.other_company, code='REG', city='Sylhet')
        cls.device = DeviceType.objects.create(
            name='Router', category=DeviceCategory.objects.create(code='INFRASTRUCTURE', name='Infrastructure'),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_directory_counts_physical_assets_and_latest_approved_audit_separately(self):
        Asset.objects.create(location=self.factory, device_type=self.device)
        for day, status, count in [(1, 'APPROVED', 20), (2, 'APPROVED', 12), (3, 'DRAFT', 30)]:
            audit = AuditSession.objects.create(location=self.factory, audit_date=date(2026, 3, day), status=status)
            AuditItem.objects.create(audit_session=audit, device_type=self.device, active_qty=count)
        response = self.client.get(reverse('location_list'), {'q': 'Dhaka'})
        self.assertEqual(response.status_code, 200)
        location = response.context['page_obj'].object_list[0]
        self.assertEqual(location.pk, self.factory.pk)
        self.assertEqual(location.tracked_assets, 1)
        self.assertEqual(location.audited_quantity, 12)
        self.assertEqual(location.latest_audit_date, date(2026, 3, 2))
        self.assertEqual(response.context['summary'], {'total': 3, 'active': 2, 'audited': 1})

    def test_directory_filters_and_role_scope(self):
        local = User.objects.create_user('directory-factory')
        local.profile.role = Role.FACTORY_ADMIN
        local.profile.save()
        local.profile.assigned_locations.set([self.factory, self.subsite])
        self.client.force_login(local)
        response = self.client.get(reverse('location_list'), {'type': 'FACTORY', 'status': 'inactive'})
        self.assertEqual([item.pk for item in response.context['page_obj']], [self.subsite.pk])
        self.assertNotContains(response, self.other_company.name)
        self.assertNotContains(response, 'Add location')
        self.assertEqual(self.client.get(reverse('location_edit', args=[self.factory.pk])).status_code, 403)

    def test_form_rejects_duplicate_ids_and_keeps_entered_values(self):
        response = self.client.post(reverse('location_create'), {
            'name': 'Pending site', 'company': self.company.pk, 'city': 'Kushtia',
            'location_type': 'FACTORY', 'code': self.factory.code.lower(), 'location_id': self.factory.location_id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('code', response.context['form'].errors)
        self.assertIn('location_id', response.context['form'].errors)
        self.assertContains(response, 'value="Kushtia"')
        self.assertFalse(Location.objects.filter(name='Pending site').exists())

    def test_company_and_hierarchy_validation(self):
        response = self.client.post(reverse('location_create'), {
            'name': 'New plant', 'company': self.other_company.pk, 'location_type': 'FACTORY',
            'parent_location': self.factory.pk,
        })
        self.assertContains(response, 'Select a parent in the same company.')
        response = self.client.post(reverse('location_edit', args=[self.factory.pk]), {
            'name': self.factory.name, 'location_type': 'FACTORY', 'parent_location': self.subsite.pk,
        })
        self.assertContains(response, 'This parent would create a location hierarchy cycle.')
        self.factory.refresh_from_db()
        self.assertIsNone(self.factory.parent_location)

    def test_create_uses_selected_company_and_keeps_codes_unique(self):
        url = reverse('location_create')
        for _ in range(2):
            response = self.client.post(url, {
                'name': 'New branch', 'company': self.other_company.pk, 'location_type': 'BRANCH',
                'parent_location': self.other.pk, 'status': 'ACTIVE',
            })
            self.assertRedirects(response, reverse('location_list'))
        self.assertEqual(
            list(Location.objects.filter(name='New branch', company=self.other_company, parent_location=self.other)
                 .order_by('pk').values_list('code', flat=True)), ['NEW-BRANCH', 'NEW-BRANCH-2'],
        )
        response = self.client.post(reverse('location_edit', args=[self.factory.pk]), {
            'name': 'Renamed factory', 'company': self.other_company.pk, 'code': 'NEWCODE', 'status': 'INACTIVE',
        })
        self.assertRedirects(response, reverse('location_list'))
        self.factory.refresh_from_db()
        self.assertFalse(self.factory.is_active)
        self.assertEqual((self.factory.company, self.factory.code), (self.company, 'MAIN'))

    def test_audit_link_preselects_an_active_visible_location(self):
        local = User.objects.create_user('audit-directory-factory')
        local.profile.role = Role.FACTORY_ADMIN
        local.profile.save()
        local.profile.assigned_locations.set([self.factory, self.subsite])
        self.client.force_login(local)
        route = reverse('audit_create')
        self.assertContains(self.client.get(reverse('location_list')), f'{route}?location={self.factory.pk}')
        response = self.client.get(route, {'location': self.factory.pk})
        self.assertEqual(response.context['selected_location_id'], self.factory.pk)
        self.assertContains(response, f'<option value="{self.factory.pk}" selected', html=False)
        for site in (self.other, self.subsite):
            self.assertEqual(self.client.get(route, {'location': site.pk}).status_code, 404)
            self.assertEqual(self.client.post(route, {'location': site.pk}).status_code, 404)

    def test_location_detail_view(self):
        """Detail view renders site specifications, hardware assets, and audit records."""
        Asset.objects.create(location=self.factory, device_type=self.device, asset_tag='TAG-TEST-001')
        url = reverse('location_detail', args=[self.factory.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Main factory')
        self.assertContains(response, 'TAG-TEST-001')
        self.assertContains(response, 'Factory annex')

    def test_location_delete_view_protection_and_deactivation(self):
        """Locations with assets cannot be hard deleted; they can be deactivated."""
        Asset.objects.create(location=self.factory, device_type=self.device)
        delete_url = reverse('location_delete', args=[self.factory.pk])

        # GET confirmation page shows protected status
        get_res = self.client.get(delete_url)
        self.assertEqual(get_res.status_code, 200)
        self.assertTrue(get_res.context['has_dependencies'])

        # Attempting hard delete redirects with error
        post_del = self.client.post(delete_url, {'action': 'delete'}, follow=True)
        self.assertEqual(post_del.status_code, 200)
        self.assertTrue(Location.objects.filter(pk=self.factory.pk).exists())

        # Deactivation action sets is_active=False safely
        post_deact = self.client.post(delete_url, {'action': 'deactivate'}, follow=True)
        self.assertEqual(post_deact.status_code, 200)
        self.factory.refresh_from_db()
        self.assertFalse(self.factory.is_active)

    def test_location_delete_view_empty_location(self):
        """Unreferenced locations can be cleanly deleted."""
        clean_loc = Location.objects.create(name='Empty Depot', company=self.company, code='EMPTY')
        delete_url = reverse('location_delete', args=[clean_loc.pk])
        post_res = self.client.post(delete_url, {'action': 'delete'}, follow=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertFalse(Location.objects.filter(pk=clean_loc.pk).exists())

