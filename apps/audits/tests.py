from io import StringIO
from datetime import date
from django.core.management import call_command
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse
from django.contrib.auth.models import User

from apps.accounts.access import Role
from apps.locations.models import Company, Location
from apps.devices.models import DeviceCategory, DeviceType
from apps.audits.models import AuditItem, AuditSession


class ManualAuditWorkflowTests(TestCase):
    def test_seed_data_creates_master_records_without_audit_counts(self):
        call_command('seed_data', stdout=StringIO())

        self.assertEqual(AuditSession.objects.count(), 0)
        self.assertEqual(AuditItem.objects.count(), 0)

    def test_offline_json_routes_are_not_registered(self):
        for path in ('/sync-json/', '/audits/1/export-json/'):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)


class AuditSessionWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Akij Test Group', short_code='AKIJ')
        cls.factory = Location.objects.create(
            company=cls.company, name='Dhaka Factory', code='DHK-FAC', location_type='FACTORY'
        )
        cls.depot = Location.objects.create(
            company=cls.company, name='Chittagong Depot', code='CTG-DEP', location_type='DEPOT'
        )
        cls.category = DeviceCategory.objects.create(name='Infrastructure', code='INFRASTRUCTURE', order=1)
        cls.device_type = DeviceType.objects.create(name='Server Rack', category=cls.category)

        cls.ho_admin = User.objects.create_user('ho-admin', password='Password123!')
        cls.ho_admin.profile.role = Role.HO_ADMIN
        cls.ho_admin.profile.save()

        cls.factory_admin = User.objects.create_user('fac-admin', password='Password123!')
        cls.factory_admin.profile.role = Role.FACTORY_ADMIN
        cls.factory_admin.profile.save()
        cls.factory_admin.profile.assigned_locations.add(cls.factory)

        cls.audit = AuditSession.objects.create(
            location=cls.factory,
            audit_date=date(2026, 3, 1),
            auditor_name='Auditor John',
            status='DRAFT'
        )

    def test_audit_list_view_and_filtering(self):
        self.client.force_login(self.ho_admin)
        response = self.client.get(reverse('audit_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dhaka Factory')
        self.assertContains(response, 'Total Audits')
        self.assertEqual(response.context['total_audits'], 1)

        # Test search filter
        response = self.client.get(reverse('audit_list'), {'q': 'Dhaka'})
        self.assertEqual(len(response.context['page_obj']), 1)

        response = self.client.get(reverse('audit_list'), {'q': 'NonExistent'})
        self.assertEqual(len(response.context['page_obj']), 0)

    def test_audit_status_workflow_transitions_and_permissions(self):
        # 1. Factory admin can submit their draft audit
        self.client.force_login(self.factory_admin)
        submit_url = reverse('audit_status_action', args=[self.audit.id])
        res = self.client.post(submit_url, {'action': 'submit', 'action_notes': 'Completed count'})
        self.assertEqual(res.status_code, 302)
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.status, 'SUBMITTED')

        # 2. Factory admin CANNOT verify or approve (PermissionDenied)
        res_verify = self.client.post(submit_url, {'action': 'verify'})
        self.assertEqual(res_verify.status_code, 403)
        res_approve = self.client.post(submit_url, {'action': 'approve'})
        self.assertEqual(res_approve.status_code, 403)

        # 3. HO Admin can verify
        self.client.force_login(self.ho_admin)
        res_verify = self.client.post(submit_url, {'action': 'verify', 'action_notes': 'Checked by HO'})
        self.assertEqual(res_verify.status_code, 302)
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.status, 'VERIFIED')
        self.assertEqual(self.audit.verified_by_name, 'ho-admin')

        # 4. HO Admin can approve and finalize
        res_approve = self.client.post(submit_url, {'action': 'approve'})
        self.assertEqual(res_approve.status_code, 302)
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.status, 'APPROVED')
        self.assertEqual(self.audit.approved_by_name, 'ho-admin')

        # 5. HO Admin can return to draft if needed
        res_return = self.client.post(submit_url, {'action': 'return_draft', 'action_notes': 'Need recount'})
        self.assertEqual(res_return.status_code, 302)
        self.audit.refresh_from_db()
        self.assertEqual(self.audit.status, 'DRAFT')

    def test_audit_create_safe_integer_handling(self):
        self.client.force_login(self.ho_admin)
        create_url = reverse('audit_create')
        # Send non-integer strings and negative values
        post_data = {
            'location': str(self.factory.id),
            'audit_date': '2026-04-10',
            'auditor_name': 'Test Auditor',
            'status': 'DRAFT',
            f'active_{self.device_type.id}': 'invalid_str',
            f'backup_{self.device_type.id}': '-5',
            f'faulty_{self.device_type.id}': '10',
            f'remarks_{self.device_type.id}': 'Tested safe int'
        }
        res = self.client.post(create_url, post_data)
        self.assertEqual(res.status_code, 302)
        new_audit = AuditSession.objects.get(location=self.factory, audit_date='2026-04-10')
        item = new_audit.items.get(device_type=self.device_type)
        self.assertEqual(item.active_qty, 0)
        self.assertEqual(item.backup_qty, 0)
        self.assertEqual(item.faulty_qty, 10)
