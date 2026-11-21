from datetime import datetime, timezone
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.access import Role
from apps.accounts.models import RoleDefinition
from apps.audits.models import AuditSession
from apps.common.models import SystemActivityLog, SystemSettings
from apps.locations.models import Company, Location


class AdministrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name='Test company', short_code='TEST')
        cls.factory = Location.objects.create(company=company, name='Assigned factory', code='A', location_type='FACTORY')
        cls.other_factory = Location.objects.create(company=company, name='Other factory', code='B', location_type='FACTORY')
        cls.depot = Location.objects.create(company=company, name='Other depot', code='C', location_type='DEPOT')
        cls.super_admin = User.objects.create_superuser('system', password='Example-setup-password-91')
        cls.ho_admin = User.objects.create_user('head-office')
        cls.ho_admin.profile.role = Role.HO_ADMIN
        cls.ho_admin.profile.save()
        cls.factory_admin = User.objects.create_user('local-factory')
        cls.factory_admin.profile.role = Role.FACTORY_ADMIN
        cls.factory_admin.profile.save()
        cls.factory_admin.profile.assigned_locations.add(cls.factory)
        cls.depot_admin = User.objects.create_user('local-depot')
        cls.depot_admin.profile.role = Role.DEPOT_ADMIN
        cls.depot_admin.profile.save()
        cls.depot_admin.profile.assigned_locations.add(cls.depot)
        cls.other_audit = AuditSession.objects.create(location=cls.other_factory, audit_date='2026-01-01')

    def test_role_dashboard_and_sidebar(self):
        self.client.force_login(self.ho_admin)
        self.assertRedirects(self.client.get('/admin/dashboard/'), '/admin/ho/dashboard/')
        response = self.client.get('/admin/ho/dashboard/')
        for label in ('User Management', 'Roles &amp; Permissions', 'Activity Logs', 'System Settings'):
            self.assertContains(response, label)
        self.assertEqual(self.client.get('/admin/super/dashboard/').status_code, 403)
        self.client.force_login(self.factory_admin)
        self.assertRedirects(self.client.get('/admin/dashboard/'), '/admin/factory/dashboard/')
        self.assertNotContains(self.client.get('/admin/factory/dashboard/'), 'User Management')
        self.client.force_login(self.depot_admin)
        self.assertRedirects(self.client.get('/admin/dashboard/'), '/admin/depot/dashboard/')
        self.assertEqual(self.client.get('/admin/factory/dashboard/').status_code, 403)
        self.client.force_login(self.super_admin)
        self.assertRedirects(self.client.get('/admin/dashboard/'), '/admin/super/dashboard/')

    def test_navigation_marks_subpages_and_limits_role_actions(self):
        self.client.force_login(self.ho_admin)
        response = self.client.get(reverse('asset_create'))
        self.assertEqual(response.context['nav_current']['label'], 'Asset Inventory')
        self.assertEqual(response.context['nav_current']['current'], 'location')
        self.assertContains(response, '<li aria-current="page">New asset</li>', html=True)
        self.assertContains(response, 'New Location')
        self.assertNotContains(response, 'Django Admin')

        self.client.force_login(self.factory_admin)
        response = self.client.get(reverse('asset_list'))
        self.assertEqual(response.context['nav_current']['current'], 'page')
        self.assertNotContains(response, 'Device Catalog')
        self.assertNotContains(response, 'User Management')
        self.assertNotContains(response, 'New Location')
        self.assertContains(response, 'New Audit')
        self.assertContains(response, 'Find in navigation')

    def test_super_admin_can_add_custom_roles_and_duplicate_names_are_rejected(self):
        self.client.force_login(self.super_admin)
        roles = reverse('administration_roles')
        create_role = reverse('administration_role_create')
        self.assertContains(self.client.get(roles), f'href="{create_role}"')
        self.assertRedirects(self.client.post(create_role, {
            'name': 'Factory Coordinator', 'base_role': Role.FACTORY_ADMIN,
            'description': 'Coordinates audits for an assigned factory.',
        }), roles)
        self.assertContains(self.client.get(roles), 'Factory Coordinator')
        self.assertTrue(SystemActivityLog.objects.filter(action='CREATE_ROLE', description__contains='Factory Coordinator').exists())
        for name in ('factory coordinator', ' Factory Admin '):
            response = self.client.post(create_role, {'name': name, 'base_role': Role.FACTORY_ADMIN})
            self.assertContains(response, 'This role name is already in use.')
        self.assertEqual(RoleDefinition.objects.count(), 1)
        response = self.client.post(create_role, {'name': 'New Superuser', 'base_role': Role.SUPER_ADMIN})
        self.assertIn('base_role', response.context['form'].errors)

    def test_custom_role_assignment_preserves_base_dashboard_and_location_scope(self):
        custom = RoleDefinition.objects.create(name='Factory Coordinator', base_role=Role.FACTORY_ADMIN)
        ho_variant = RoleDefinition.objects.create(name='Central Operations', base_role=Role.HO_ADMIN)
        role_url = reverse('administration_role_create')
        self.client.force_login(self.ho_admin)
        self.assertEqual(self.client.get(role_url).status_code, 403)
        self.assertEqual(self.client.post(role_url, {'name': 'Blocked', 'base_role': Role.HO_ADMIN}).status_code, 403)
        user_url = reverse('administration_user_create')
        data = {
            'username': 'custom-coordinator', 'role': f'custom:{custom.pk}', 'is_active': 'on',
            'password': 'Example-issued-password-72', 'assigned_locations': [self.depot.pk],
        }
        self.assertContains(self.client.post(user_url, data), 'Assignments must match the selected role')
        forbidden = {**data, 'role': f'custom:{ho_variant.pk}'}
        self.assertIn('role', self.client.post(user_url, forbidden).context['form'].errors)
        data['assigned_locations'] = [self.factory.pk]
        self.assertRedirects(self.client.post(user_url, data), reverse('administration_users'))
        account = User.objects.get(username=data['username'])
        self.assertEqual((account.profile.role, account.profile.custom_role), (Role.FACTORY_ADMIN, custom))
        filtered = self.client.get(reverse('administration_users'), {'role': f'custom:{custom.pk}'})
        self.assertEqual(list(filtered.context['page_obj']), [account])
        self.assertContains(filtered, custom.name)

        self.client.force_login(account)
        response = self.client.get(reverse('factory_dashboard'))
        self.assertContains(response, custom.name)
        self.assertEqual(self.client.get(reverse('ho_dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('audit_detail', args=[self.other_audit.pk])).status_code, 404)

    def test_pending_username_does_not_grant_ho_permissions(self):
        self.client.force_login(User.objects.create_user('auditor'))
        self.assertEqual(self.client.get(reverse('administration_roles')).status_code, 403)

    def test_local_scope_covers_operational_routes_and_logs(self):
        self.client.force_login(self.factory_admin)
        response = self.client.get(reverse('location_list'))
        self.assertContains(response, self.factory.name)
        self.assertNotContains(response, self.other_factory.name)
        self.assertNotContains(response, self.depot.name)
        paths = ['audit_detail', 'audit_edit', 'audit_print']
        for name in paths:
            self.assertEqual(self.client.get(reverse(name, args=[self.other_audit.pk])).status_code, 404)
        workbook = load_workbook(BytesIO(self.client.get(reverse('export_excel_matrix')).content))
        headers = [cell.value for cell in workbook.active[4]]
        self.assertIn(f'[{self.factory.location_id}] {self.factory.name}', headers)
        self.assertNotIn(f'[{self.other_factory.location_id}] {self.other_factory.name}', headers)
        for path in ('/admin/users/', '/admin/roles/', '/admin/settings/', '/admin/activity/', '/logs/'):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.factory_admin.profile.assigned_locations.clear()
        self.assertNotContains(self.client.get(reverse('location_list')), self.factory.name)

    def test_ho_user_creation_and_assignment_validation(self):
        self.client.force_login(self.ho_admin)
        data = {
            'username': 'new-local-admin',
            'is_active': 'on',
            'password': 'Example-issued-password-72',
            'role': Role.FACTORY_ADMIN,
            'assigned_locations': [self.depot.pk],
            'phone_number': '+880 1700 000000',
            'designation': 'IT Officer, Factory',
        }
        url = reverse('administration_user_create')
        self.assertContains(self.client.post(url, data), 'Assignments must match the selected role')
        data['assigned_locations'] = [self.factory.pk, self.other_factory.pk]
        self.assertRedirects(self.client.post(url, data), reverse('administration_users'))
        account = User.objects.get(username=data['username'])
        self.assertTrue(account.check_password(data['password']))
        self.assertFalse(account.is_staff)
        self.assertEqual(account.profile.assigned_locations.count(), 2)
        self.assertEqual(account.profile.phone_number, data['phone_number'])
        self.assertEqual(account.profile.designation, data['designation'])
        form_page = self.client.get(reverse('administration_user_edit', args=[account.pk]))
        for section in ('Account details', 'Work information', 'Role and location access'):
            self.assertContains(form_page, section)
        self.assertContains(form_page, data['phone_number'])
        self.assertContains(form_page, 'Last sign-in')
        self.assertTrue(SystemActivityLog.objects.filter(action='CREATE_USER', description__contains='Locations:').exists())
        self.assertEqual(self.client.get(reverse('administration_user_edit', args=[self.super_admin.pk])).status_code, 404)

    def test_ho_cannot_create_another_ho_admin(self):
        self.client.force_login(self.ho_admin)
        response = self.client.post(reverse('administration_user_create'), {
            'username': 'unauthorized-role',
            'role': Role.HO_ADMIN,
            'password': 'Example-issued-password-72',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='unauthorized-role').exists())

    def test_pending_account_requires_review(self):
        pending = User.objects.create_user('previous-account')
        pending.profile.assigned_locations.add(self.factory)
        self.client.force_login(pending)
        self.assertContains(self.client.get(reverse('dashboard')), 'Role assignment required', status_code=403)
        self.assertEqual(self.client.get(reverse('asset_create')).status_code, 403)
        self.client.force_login(self.ho_admin)
        self.assertContains(self.client.get(reverse('administration_users'), {'role': Role.PENDING}), pending.username)

    def test_user_filters_combine_role_status_and_location(self):
        self.client.force_login(self.ho_admin)
        self.factory_admin.is_active = False
        self.factory_admin.save(update_fields=['is_active'])
        filters = {'role': Role.FACTORY_ADMIN, 'status': 'inactive', 'location': self.factory.pk}
        response = self.client.get(reverse('administration_users'), filters)
        self.assertEqual(list(response.context['page_obj']), [self.factory_admin])
        filters['location'] = self.other_factory.pk
        self.assertEqual(list(self.client.get(reverse('administration_users'), filters).context['page_obj']), [])

    def test_settings_are_persisted_enforced_and_logged(self):
        url = reverse('administration_settings')
        self.client.force_login(self.ho_admin)
        self.assertContains(self.client.get(url), 'Super Admin can change these settings')
        self.assertEqual(self.client.post(url, {'session_minutes': 60, 'activity_page_size': 10}).status_code, 403)
        self.client.force_login(self.super_admin)
        self.assertRedirects(self.client.post(url, {'session_minutes': 60, 'activity_page_size': 10}), url)
        self.assertEqual(SystemSettings.current().session_minutes, 60)
        self.assertEqual(self.client.get(reverse('activity_logs')).context['page_obj'].paginator.per_page, 10)
        self.assertTrue(SystemActivityLog.objects.filter(action='UPDATE_SYSTEM_SETTINGS').exists())
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('login'), {
            'username': self.super_admin.username, 'password': 'Example-setup-password-91',
        }), reverse('dashboard'), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get_expiry_age(), 3600)

    def test_list_and_support_settings_take_effect(self):
        url = reverse('administration_settings')
        self.client.force_login(self.super_admin)
        data = {'session_minutes': 60, 'activity_page_size': 20, 'user_page_size': 12, 'support_email': 'it@example.test'}
        self.assertRedirects(self.client.post(url, data), url)
        self.assertEqual(self.client.get(reverse('administration_users')).context['page_obj'].paginator.per_page, 12)
        self.client.force_login(User.objects.create_user('needs-help'))
        self.assertContains(self.client.get(reverse('dashboard')), 'mailto:it@example.test', status_code=403)

    def test_log_date_filters_use_local_dates_and_reject_reversed_ranges(self):
        self.client.force_login(self.ho_admin)
        old = SystemActivityLog.objects.create(action='UPDATE_USER', module='Administration', description='Earlier event')
        event = SystemActivityLog.objects.create(action='UPDATE_USER', module='Administration', description='Matching event')
        SystemActivityLog.objects.filter(pk=old.pk).update(created_at=datetime(2026, 11, 20, 17, 59, tzinfo=timezone.utc))
        SystemActivityLog.objects.filter(pk=event.pk).update(created_at=datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc))
        url = reverse('activity_logs')
        response = self.client.get(url, {'date_from': '2026-11-21', 'date_to': '2026-11-21'})
        self.assertContains(response, 'Matching event')
        self.assertNotContains(response, 'Earlier event')
        response = self.client.get(url, {'date_from': '2026-11-21', 'date_to': '2026-11-20'})
        self.assertContains(response, 'The end date must be on or after the start date.')
        self.assertEqual(response.context['total_count'], 0)

    def test_email_based_login(self):
        self.super_admin.email = 'superadmin@akij.net'
        self.super_admin.save(update_fields=['email'])
        self.client.logout()

        # 1. Sign in using exact email
        response = self.client.post(reverse('login'), {
            'username': 'superadmin@akij.net',
            'password': 'Example-setup-password-91'
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        self.client.logout()

        # 2. Sign in using case-insensitive email
        response = self.client.post(reverse('login'), {
            'username': 'SUPERADMIN@AKIJ.NET',
            'password': 'Example-setup-password-91'
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        self.client.logout()

        # 3. Sign in using username (backwards compatibility)
        response = self.client.post(reverse('login'), {
            'username': self.super_admin.username,
            'password': 'Example-setup-password-91'
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

        self.client.logout()

        # 4. Failed sign-in with wrong email
        response = self.client.post(reverse('login'), {
            'username': 'nonexistent@akij.net',
            'password': 'WrongPassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email or password.')


