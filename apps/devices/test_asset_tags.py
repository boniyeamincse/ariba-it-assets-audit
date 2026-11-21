from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.access import Role
from apps.common.models import SystemSettings
from apps.devices.models import Asset, AssetIdSequence, DeviceCategory, DeviceType, IssuedAssetTag
from apps.locations.models import Company, Location


class AssetTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('asset-tag-admin')
        cls.factory_user = User.objects.create_user('asset-tag-factory')
        cls.factory_user.profile.role = Role.FACTORY_ADMIN
        cls.factory_user.profile.save()
        cls.company = Company.objects.create(short_code='APL')
        cls.head_office = Location.objects.create(company=cls.company, code='TAG-HO', location_type='HEAD_OFFICE')
        cls.factory = Location.objects.create(company=cls.company, code='TAG-PLANT')
        cls.factory_user.profile.assigned_locations.add(cls.factory)
        cls.catalogue = DeviceCategory.objects.create(code='INFRASTRUCTURE', name='Infrastructure')
        cls.router = DeviceType.objects.create(category=cls.catalogue, name='Edge Router')
        cls.scanner = DeviceType.objects.create(category=cls.catalogue, name='Document Scanner')
        cls.nas = DeviceType.objects.create(category=cls.catalogue, name='NAS Storage')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_defaults_prefix_free_global_sequence_and_stored_category_codes(self):
        settings = SystemSettings.current()
        settings.options['asset_id_location_code'] = 'FORCED'
        settings.save()
        devices = (self.router, self.scanner, self.nas)
        tags = [Asset.objects.create(device_type=device, location=self.head_office).asset_tag for device in devices]
        self.assertEqual(tags, ['APL-ROU-10001', 'APL-PRT-10002', 'APL-NAS-10003'])
        self.router.name = 'Edge appliance'
        self.router.save()
        after_rename = Asset.objects.create(device_type=self.router, location=self.head_office)
        self.assertEqual(after_rename.asset_tag, 'APL-ROU-10004')
        self.router.tag_category_code = 'FWL'
        with self.assertRaisesMessage(ValidationError, 'code is locked'):
            self.router.save()

    def test_retirement_locks_tag_and_reservation_survives_hard_delete(self):
        asset = Asset.objects.create(asset_tag='Tag-legacy', device_type=self.router, location=self.factory)
        form_data = {'asset_tag': 'TAG-LEGACY', 'device_type': self.router.pk, 'location': self.factory.pk, 'status': 'IN_USE'}
        response = self.client.post(reverse('asset_create'), form_data)
        self.assertContains(response, 'This asset tag has already been issued.', status_code=400)
        edit_url = reverse('asset_edit', args=[asset.pk])
        response = self.client.post(edit_url, {**form_data, 'asset_tag': 'RETAG'})
        self.assertContains(response, 'An issued asset tag cannot be changed.', status_code=400)

        retirement = reverse('asset_retire', args=[asset.pk])
        self.assertRedirects(self.client.post(retirement), reverse('asset_detail', args=[asset.pk]))
        asset.refresh_from_db()
        self.assertEqual(asset.status, 'SCRAP')
        self.assertIsNotNone(asset.retired_at)
        self.assertFalse(asset.is_active)
        self.assertEqual(self.client.post(edit_url, form_data).status_code, 403)

        filename = SimpleUploadedFile('tags.csv', b'asset_tag,device_type,location,status\nTAG-LEGACY,Edge Router,TAG-PLANT,IN_USE\n')
        result = self.client.post(reverse('asset_import_csv'), {'csv_file': filename, 'update_existing': 'yes'})
        self.assertContains(result, 'belongs to a retired asset')
        asset.delete()  # Verify that an out-of-band cleanup cannot release the reservation.
        self.assertTrue(IssuedAssetTag.objects.filter(pk='TAG-LEGACY').exists())
        with self.assertRaisesMessage(ValidationError, 'already been issued'):
            Asset.objects.create(asset_tag='TAG-LEGACY', device_type=self.router, location=self.factory)

    def test_move_preserves_tag_even_across_companies(self):
        asset = Asset.objects.create(device_type=self.router, location=self.head_office)
        other_company = Company.objects.create(short_code='AJML')
        new_location = Location.objects.create(company=other_company, code='OTHER')
        response = self.client.post(reverse('asset_edit', args=[asset.pk]), {
            'asset_tag': asset.asset_tag, 'device_type': self.router.pk, 'location': new_location.pk, 'status': 'IN_USE',
        })
        self.assertRedirects(response, reverse('asset_list'))
        asset.refresh_from_db()
        self.assertEqual((asset.location_id, asset.asset_tag), (new_location.pk, 'APL-ROU-10001'))
        self.assertEqual(asset.owning_company, self.company)
        response = self.client.post(reverse('asset_edit', args=[asset.pk]), {
            'asset_tag': asset.asset_tag, 'device_type': self.router.pk, 'location': new_location.pk,
            'owning_company': other_company.pk, 'status': 'IN_USE',
        })
        self.assertRedirects(response, reverse('asset_list'))
        asset.refresh_from_db()
        self.assertEqual((asset.owning_company, asset.asset_tag), (other_company, 'APL-ROU-10001'))

    def test_sequence_exhaustion_keeps_counter_and_reservations_unchanged(self):
        AssetIdSequence.objects.update_or_create(pk=1, defaults={'last_number': 99999})
        with self.assertRaisesMessage(ValidationError, 'sequence is exhausted'):
            Asset.objects.create(device_type=self.router, location=self.head_office)
        self.assertEqual(AssetIdSequence.objects.get(pk=1).last_number, 99999)
        self.assertEqual(IssuedAssetTag.objects.count(), 0)

    def test_preview_shared_with_generator_and_qr_detail_respects_scope(self):
        preview = reverse('asset_id_preview')
        self.assertEqual(self.client.get(preview).json()['tag'], 'APL-ROU-10001')
        options = {
            'asset_id_include_company': 'on', 'asset_id_include_category': 'on', 'asset_id_location_code': 'FORCED',
            'asset_id_start': 10001, 'asset_id_length': 5, 'asset_id_separator': '-',
        }
        self.assertEqual(self.client.get(preview, options).json()['tag'], 'APL-ROU-10001')
        options['asset_id_include_location'] = 'on'
        self.assertEqual(self.client.get(preview, options).json()['tag'], 'APL-FORCED-ROU-10001')

        asset = Asset.objects.create(device_type=self.router, location=self.head_office)
        detail = reverse('asset_detail', args=[asset.pk])
        qr = reverse('asset_label_qr', args=[asset.pk])
        self.assertEqual(self.client.get(qr).status_code, 404)
        settings = SystemSettings.current()
        settings.options['application_url'] = 'https://inventory.example.test'
        settings.save()
        self.assertContains(self.client.get(detail), f'https://inventory.example.test{detail}')
        image = self.client.get(qr)
        self.assertContains(image, '<svg')
        self.assertEqual(image.headers['Content-Type'], 'image/svg+xml')
        self.client.force_login(self.factory_user)
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.get(qr).status_code, 404)
