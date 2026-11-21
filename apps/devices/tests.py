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
        DeviceCategory.objects.all().delete()
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


class SoftwareLicenseManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('slm-admin')
        cls.company = Company.objects.create(name='Akij Plastics Ltd', short_code='APL')
        cls.location = Location.objects.create(company=cls.company, code='HO', name='Head Office')
        cls.software_category = DeviceCategory.objects.create(code='SFT', name='Software & Applications')
        cls.os_type = DeviceType.objects.create(category=cls.software_category, name='Operating System')
        cls.cad_type = DeviceType.objects.create(category=cls.software_category, name='Engineering CAD')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_software_list_view_and_kpis(self):
        # Genuine software
        Asset.objects.create(
            asset_tag='APL-SFT-10001',
            asset_nature='LOGICAL',
            device_type=self.os_type,
            location=self.location,
            brand='Microsoft',
            model_name='Windows Server 2022 Datacenter',
            compliance_status='GENUINE',
            risk_level='LOW',
            remediation_plan='COMPLIANT',
            seats_purchased=10,
            seats_allocated=8,
        )
        # Cracked software
        Asset.objects.create(
            asset_tag='APL-SFT-10002',
            asset_nature='LOGICAL',
            device_type=self.cad_type,
            location=self.location,
            brand='Autodesk',
            model_name='AutoCAD 2023 Cracked',
            compliance_status='CRACKED_PIRATED',
            risk_level='HIGH',
            remediation_plan='PURCHASE_OFFICIAL',
            seats_purchased=0,
            seats_allocated=5,
        )

        response = self.client.get(reverse('software_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_software'], 2)
        self.assertEqual(response.context['cracked_count'], 1)
        self.assertEqual(response.context['genuine_count'], 1)
        self.assertEqual(response.context['high_critical_risk'], 1)
        self.assertEqual(response.context['piracy_percentage'], 50.0)
        self.assertContains(response, 'CRACKED / PIRATED')
        self.assertContains(response, 'AutoCAD 2023 Cracked')
        self.assertContains(response, 'Windows Server 2022 Datacenter')

    def test_cracked_software_risk_auto_escalation_on_creation(self):
        response = self.client.post(reverse('asset_create'), {
            'asset_nature': 'LOGICAL',
            'location': self.location.pk,
            'device_type': self.cad_type.pk,
            'brand': 'Adobe',
            'model_name': 'Photoshop CC Keygen',
            'status': 'IN_USE',
            'compliance_status': 'CRACKED_PIRATED',
            'risk_level': 'LOW',  # Submitting LOW should be auto-escalated to HIGH
            'remediation_plan': 'COMPLIANT',  # Should be escalated to PURCHASE_OFFICIAL
            'seats_purchased': 0,
            'seats_allocated': 3,
        })
        self.assertEqual(response.status_code, 302)
        asset = Asset.objects.get(model_name='Photoshop CC Keygen')
        self.assertEqual(asset.compliance_status, 'CRACKED_PIRATED')
        self.assertEqual(asset.risk_level, 'HIGH')
        self.assertEqual(asset.remediation_plan, 'PURCHASE_OFFICIAL')

    def test_compliance_and_risk_filtering(self):
        Asset.objects.create(
            asset_tag='APL-SFT-20001',
            asset_nature='LOGICAL',
            device_type=self.os_type,
            location=self.location,
            model_name='Debian GNU/Linux',
            compliance_status='FREE_OPEN_SOURCE',
            risk_level='LOW',
        )
        Asset.objects.create(
            asset_tag='APL-SFT-20002',
            asset_nature='LOGICAL',
            device_type=self.cad_type,
            location=self.location,
            model_name='SolidWorks Pirated',
            compliance_status='CRACKED_PIRATED',
            risk_level='CRITICAL',
        )

        response = self.client.get(reverse('software_list'), {'compliance': 'CRACKED_PIRATED'})
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].model_name, 'SolidWorks Pirated')

        response = self.client.get(reverse('software_list'), {'risk': 'CRITICAL'})
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].model_name, 'SolidWorks Pirated')

