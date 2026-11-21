from datetime import date
from io import StringIO
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from apps.accounts.access import Role
from apps.accounts.settings_forms import CATEGORIES, FIELDS
from apps.common.models import SystemSettings
from apps.common.management.commands.run_system_backup import create_database_backup
from apps.common.preferences import preferences
from apps.devices.models import Asset, DeviceCategory, DeviceType
from apps.locations.models import Company, Location


class SystemSettingsIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('settings-root', password='Super-secret-settings-932')
        cls.ho = User.objects.create_user('settings-ho', password='Head-office-unique-173')
        cls.ho.profile.role = Role.HO_ADMIN
        cls.ho.profile.save()
        company = Company.objects.create(name='Test company', short_code='AMFL')
        cls.location = Location.objects.create(company=company, name='Head Office', code='HO', location_type='HEAD_OFFICE')
        category = DeviceCategory.objects.create(code='INFRASTRUCTURE', name='Infrastructure')
        cls.device = DeviceType.objects.create(category=category, name='Router')

    def setUp(self):
        self.client.force_login(self.superuser)

    def setting_url(self, section):
        return reverse('administration_settings_section', args=[section])

    def update(self, section, **changes):
        config = preferences()
        values = {key: config[key] for key in FIELDS[section] if key in config and config[key] is not False}
        values.update(changes)
        url = self.setting_url(section)
        response = self.client.post(url, values)
        if response.status_code != 302:
            self.fail(str(response.context['form'].errors))
        self.assertRedirects(response, url)

    def test_all_tabs_render_and_ho_cannot_save(self):
        for section, title in CATEGORIES.items():
            self.assertContains(self.client.get(self.setting_url(section)), escape(title))
        self.assertContains(self.client.get(self.setting_url('asset-id')), 'AST-AMFL-HO-NET-00001')
        self.client.force_login(self.ho)
        url = self.setting_url('general')
        self.assertContains(self.client.get(url), 'Super Admin can change these settings')
        self.assertEqual(self.client.post(url, {'application_name': 'Restricted'}).status_code, 403)

    def test_general_branding_landing_and_maintenance(self):
        self.update('general', application_name='Operations Portal', organization_name='Sample Group', default_landing_page='assets')
        self.assertRedirects(self.client.get('/'), reverse('asset_list'))
        self.assertContains(self.client.get(reverse('asset_list')), 'Operations Portal')
        self.update('general', maintenance_mode='on')
        self.client.force_login(self.ho)
        self.assertContains(self.client.get(reverse('asset_list')), 'undergoing maintenance', status_code=503)
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(self.setting_url('general')), 'Operations Portal')

    def test_asset_ids_defaults_and_classification_apply_only_as_expected(self):
        self.update(
            'asset-id', asset_id_prefix='AST', asset_id_company_code='AMFL',
            asset_id_location_code='HO', asset_id_category_code='NET', asset_id_start=1,
        )
        self.update('assets', default_warranty_months=36, asset_currency='usd', asset_conditions='New\nRefurbished')
        asset_url = reverse('asset_create')
        self.assertContains(self.client.get(asset_url), 'Refurbished')
        response = self.client.post(asset_url, {
            'asset_tag': '', 'location': self.location.pk, 'device_type': self.device.pk,
            'status': 'IN_USE', 'condition': 'Refurbished', 'purchase_date': '2024-02-29',
        })
        self.assertRedirects(response, reverse('asset_list'))
        asset = Asset.objects.get(asset_tag='AST-AMFL-HO-NET-00001')
        self.assertEqual((asset.condition, asset.currency, asset.warranty_expiry), ('Refurbished', 'USD', date(2027, 2, 28)))
        manual = Asset.objects.create(asset_tag='MANUAL-001', location=self.location, device_type=self.device)
        self.update('asset-id', asset_id_prefix='LAB')
        following = Asset.objects.create(location=self.location, device_type=self.device)
        self.assertEqual(following.asset_tag, 'LAB-AMFL-HO-NET-00002')
        manual.refresh_from_db()
        self.assertEqual(manual.asset_tag, 'MANUAL-001')

    def test_password_and_lockout_policies(self):
        self.update('access', minimum_password_length=16, password_complexity='on', max_login_attempts=2)
        response = self.client.post(reverse('administration_user_create'), {
            'username': 'candidate', 'password': 'Simplepass13', 'role': Role.HO_ADMIN, 'is_active': 'on',
        })
        self.assertContains(response, 'Use at least 16 characters.')
        self.client.logout()
        for _ in range(2):
            self.client.post(reverse('login'), {'username': self.ho.username, 'password': 'incorrect'})
        response = self.client.post(reverse('login'), {'username': self.ho.username, 'password': 'Head-office-unique-173'})
        self.assertContains(response, 'temporarily locked', status_code=429)

    def test_csv_import_applies_configured_asset_id_and_classification(self):
        self.update('asset-id', asset_id_company_code='AMFL', asset_id_location_code='HO', asset_id_category_code='NET')
        response = self.client.post(reverse('asset_import_csv'), {
            'csv_file': SimpleUploadedFile('assets.csv', b'asset_tag,device_type,location,status,asset_condition\n,Router,HO,IN_USE,Good\n'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Asset.objects.get(asset_tag='AST-AMFL-HO-NET-00001').condition, 'Good')

    def test_ip_policy_applies_after_save_and_preserves_current_admin_access(self):
        self.update('access', allowed_ip_addresses='127.0.0.1')
        self.assertEqual(self.client.get(self.setting_url('access'), REMOTE_ADDR='192.0.2.12').status_code, 403)
        self.assertContains(self.client.get(self.setting_url('access')), 'Allowed IP addresses')
        config = preferences()
        payload = {key: config[key] for key in FIELDS['access'] if key in config and config[key] is not False}
        payload['allowed_ip_addresses'] = '192.0.2.12'
        response = self.client.post(self.setting_url('access'), payload)
        self.assertContains(response, 'Include your current network')
        self.assertEqual(preferences()['allowed_ip_addresses'], '127.0.0.1/32')

    def test_asset_notification_is_delivered_once_for_creation(self):
        self.update(
            'notifications', email_notifications='on', notify_asset_created='on',
            notification_recipients='it@example.test',
        )
        with self.captureOnCommitCallbacks(execute=True):
            asset = Asset.objects.create(asset_tag='NOTIFY-01', location=self.location, device_type=self.device)
        self.assertEqual(mail.outbox[0].subject, 'New asset created: NOTIFY-01')
        with self.captureOnCommitCallbacks(execute=True):
            asset.brand = 'Test change'
            asset.save()
        self.assertEqual(len(mail.outbox), 1)

    def test_media_backup_records_success_and_does_not_create_duplicates(self):
        with TemporaryDirectory() as working, TemporaryDirectory() as media:
            Path(media, 'evidence.txt').write_text('Synthetic evidence')
            with override_settings(SYSTEM_BACKUP_ROOT=working, MEDIA_ROOT=media):
                self.update('backup', automatic_backups='on', backup_database=False, backup_media='on')
                call_command('run_system_backup', now=True, stdout=StringIO())
                archives = list(Path(working).glob('audit-backup-*/media.tar.gz'))
                self.assertEqual(len(archives), 1)
                self.assertEqual(preferences()['last_backup_status'], 'Successful')
                call_command('run_system_backup', now=True, stdout=StringIO())
                self.assertEqual(len(list(Path(working).glob('audit-backup-*/media.tar.gz'))), 1)

    def test_sqlite_backup_copies_data_and_leaves_original_intact(self):
        with TemporaryDirectory() as working:
            origin = Path(working, 'origin.sqlite3')
            target = Path(working, 'copy.sqlite3')
            with sqlite3.connect(origin) as db:
                db.execute('CREATE TABLE entries (description TEXT)')
                db.execute('INSERT INTO entries VALUES (?)', ['Synthetic record'])
            with patch('apps.common.management.commands.run_system_backup.connections') as connections:
                connections.__getitem__.return_value.settings_dict = {'NAME': origin, 'ENGINE': 'django.db.backends.sqlite3'}
                create_database_backup(target)
            for database in (origin, target):
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT description FROM entries').fetchall(), [('Synthetic record',)])

    def test_daily_digest_groups_asset_creation_notifications(self):
        self.update(
            'notifications', email_notifications='on', notify_asset_created='on',
            notification_frequency='daily', notification_recipients='it@example.test',
        )
        Asset.objects.create(asset_tag='DIGEST-01', location=self.location, device_type=self.device)
        Asset.objects.create(asset_tag='DIGEST-02', location=self.location, device_type=self.device)
        call_command('send_asset_digest', dry_run=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)
        call_command('send_asset_digest', stdout=StringIO())
        call_command('send_asset_digest', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('DIGEST-01', mail.outbox[0].body)
        self.assertIn('DIGEST-02', mail.outbox[0].body)

    def test_all_14_sections_render_subtitles_and_update(self):
        from apps.accounts.settings_forms import SECTION_METADATA
        self.assertEqual(len(CATEGORIES), 14)
        for section, meta in SECTION_METADATA.items():
            response = self.client.get(self.setting_url(section))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, escape(meta['title']))
            self.assertContains(response, escape(meta['subtitle']))
            self.assertContains(response, 'Admin only')

        self.update('email', smtp_host='mail.akij.net', smtp_port=587, smtp_use_tls='on', smtp_from_email='support@akij.net')
        self.assertEqual(preferences()['smtp_host'], 'mail.akij.net')
        self.assertEqual(preferences()['smtp_port'], 587)

        self.update('security', minimum_password_length=12, lockout_minutes=30)
        self.assertEqual(preferences()['minimum_password_length'], 12)
        self.assertEqual(preferences()['lockout_minutes'], 30)

        self.update('integration', enable_api='on', erp_sync_enabled='on', erp_endpoint_url='https://erp.akij.net/api/v1/sync')
        self.assertEqual(preferences()['erp_endpoint_url'], 'https://erp.akij.net/api/v1/sync')

        self.update('maintenance', maintenance_message='Maintenance in progress for Akij systems')
        self.assertEqual(preferences()['maintenance_message'], 'Maintenance in progress for Akij systems')

