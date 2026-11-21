from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.access import Role
from apps.devices.models import Asset, DeviceCategory, DeviceType
from apps.locations.models import Company, Location


class CategoryButtonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rename_buttons = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'button' and 'data-rename-category' in attrs:
            self.rename_buttons.append(attrs)


class DeviceCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('catalog-admin')
        cls.network = DeviceCategory.objects.create(code='INFRASTRUCTURE', name="Engineer's Network")
        cls.users = DeviceCategory.objects.create(code='USERS', name='User Equipment')
        cls.archived_category = DeviceCategory.objects.create(code='LEGACY', name='Legacy Equipment', is_active=False)
        cls.router = DeviceType.objects.create(category=cls.network, name='Router')
        cls.cable = DeviceType.objects.create(category=cls.network, name='Cable', is_count_only=True, is_active=False)
        cls.legacy = DeviceType.objects.create(category=cls.archived_category, name='Legacy switch', is_count_only=True)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_status_and_tracking_filters_combine(self):
        url = reverse('category_list')
        response = self.client.get(url, {'status': 'archived', 'tracking': 'bulk'})
        self.assertEqual({device.pk for group in response.context['categories'] for device in group.devices.all()},
                         {self.legacy.pk, self.cable.pk})

        response = self.client.get(url, {'status': 'active', 'tracking': 'tagged'})
        self.assertEqual({device.pk for group in response.context['categories'] for device in group.devices.all()},
                         {self.router.pk})

        response = self.client.get(url, {'status': 'active', 'tracking': 'bulk'})
        self.assertContains(response, 'No device types match the selected filters.')

    def test_rename_button_keeps_apostrophes_and_filters(self):
        url = reverse('category_list') + '?status=active&tracking=tagged'
        parser = CategoryButtonParser()
        parser.feed(self.client.get(url).content.decode())
        button = next(item for item in parser.rename_buttons if item['data-category-id'] == str(self.network.pk))
        self.assertEqual(button['data-category-name'], "Engineer's Network")
        self.assertNotIn('onclick', button)
        self.assertRedirects(self.client.post(url, {
            'action_type': 'edit_category',
            'category_id': self.network.pk,
            'category_name': "Engineer's Network Equipment",
        }), url)
        self.network.refresh_from_db()
        self.assertEqual(self.network.name, "Engineer's Network Equipment")

    def test_asset_link_uses_exact_type_and_respects_location_scope(self):
        other_router = DeviceType.objects.create(category=self.users, name='Router')
        company = Company.objects.create(short_code='QA')
        factory = Location.objects.create(company=company, code='FACTORY-A')
        unassigned = Location.objects.create(company=company, code='FACTORY-B')
        selected_asset = Asset.objects.create(asset_tag='EXACT-ROUTER', device_type=self.router, location=factory)
        Asset.objects.create(asset_tag='OTHER-ROUTER', device_type=other_router, location=factory)
        Asset.objects.create(asset_tag='OUTSIDE-ROUTER', device_type=self.router, location=unassigned)

        asset_url = reverse('asset_list')
        self.assertContains(self.client.get(reverse('category_list')), f'{asset_url}?device_type={self.router.pk}')
        factory_admin = User.objects.create_user('catalog-factory')
        factory_admin.profile.role = Role.FACTORY_ADMIN
        factory_admin.profile.save(update_fields=['role'])
        factory_admin.profile.assigned_locations.add(factory)
        self.client.force_login(factory_admin)
        response = self.client.get(asset_url, {'device_type': self.router.pk})
        self.assertContains(response, 'Remove device type filter')
        self.assertEqual(list(response.context['page_obj']), [selected_asset])
        self.assertEqual(self.client.get(asset_url, {'device_type': 'not-a-number'}).status_code, 404)

        Asset.objects.bulk_create([
            Asset(asset_tag=f'PAGE-ROUTER-{number}', device_type=self.router, location=factory)
            for number in range(25)
        ])
        response = self.client.get(asset_url, {'device_type': self.router.pk})
        self.assertContains(response, f'?device_type={self.router.pk}&amp;page=2')
        self.assertEqual(self.client.get(asset_url, {'device_type': self.router.pk, 'page': 2}).context['total_assets'], 26)
