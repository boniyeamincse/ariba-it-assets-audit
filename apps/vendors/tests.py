from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.devices.models import Asset, DeviceCategory, DeviceType
from apps.locations.models import Company, Location
from apps.vendors.models import (
    Vendor, VendorContact, VendorContract, VendorRMA, VendorEvaluation
)


class VendorModelTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(
            name="Smart Technologies BD Ltd",
            category="HARDWARE_OEM",
            status="ACTIVE",
            email="support@smart-bd.com",
            phone="+8801700000000"
        )

    def test_vendor_code_auto_generation(self):
        """Test that vendor_code is automatically created with prefix VND-YYYY-XXXX."""
        self.assertTrue(self.vendor.vendor_code.startswith("VND-"))
        self.assertIn(str(date.today().year), self.vendor.vendor_code)

    def test_vendor_str_representation(self):
        self.assertIn("Smart Technologies BD Ltd", str(self.vendor))

    def test_evaluation_and_rating_recalculation(self):
        """Test that submitting evaluations calculates weighted score and updates vendor overall_rating."""
        eval1 = VendorEvaluation.objects.create(
            vendor=self.vendor,
            review_period="Q1 2026",
            delivery_score=5,
            quality_score=4,
            support_score=4,
            pricing_score=5,
        )
        # Weighted: (5*0.30) + (4*0.25) + (4*0.25) + (5*0.20) = 1.5 + 1.0 + 1.0 + 1.0 = 4.50
        self.assertEqual(eval1.composite_score, Decimal('4.50'))
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.overall_rating, Decimal('4.50'))


class VendorContractTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name="Flora Systems")

    def test_contract_date_validation(self):
        """End date cannot be prior to start date."""
        contract = VendorContract(
            vendor=self.vendor,
            contract_number="AMC-INVALID-01",
            title="Invalid Dates AMC",
            start_date=date.today(),
            end_date=date.today() - timedelta(days=5),
        )
        with self.assertRaises(ValidationError):
            contract.clean()

    def test_contract_urgency_and_days_until_expiry(self):
        today = date.today()
        # Active contract expiring in 10 days -> critical
        contract_critical = VendorContract.objects.create(
            vendor=self.vendor,
            contract_number="AMC-CRITICAL-01",
            title="Critical Contract",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=10),
        )
        self.assertEqual(contract_critical.urgency_level, 'critical')
        self.assertEqual(contract_critical.days_until_expiry, 10)
        self.assertFalse(contract_critical.is_expired)

        # Expired contract -> expired
        contract_expired = VendorContract.objects.create(
            vendor=self.vendor,
            contract_number="AMC-EXPIRED-01",
            title="Expired Contract",
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=5),
        )
        self.assertEqual(contract_expired.urgency_level, 'expired')
        self.assertTrue(contract_expired.is_expired)


class VendorViewsSecurityAndWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Akij Shipping", short_code="ASL")
        self.location = Location.objects.create(name="Chattogram Depot", code="CTG-DEP", company=self.company)
        self.category = DeviceCategory.objects.create(name="Infrastructure", code="INFRASTRUCTURE")
        self.device_type = DeviceType.objects.create(name="Core Switch", category=self.category, tag_category_code="SWT")
        self.asset = Asset.objects.create(
            device_type=self.device_type,
            location=self.location,
            brand="Cisco",
            model_name="Catalyst 9300",
            asset_tag="ASL-CTG-NETW-0001"
        )

        # Super Admin User
        self.admin_user = User.objects.create_superuser('superadmin', 'admin@akij.net', 'Secret123!')
        self.admin_profile = self.admin_user.profile

        # Unit Officer User
        self.unit_user = User.objects.create_user('unituser', 'unit@akij.net', 'Secret123!')
        self.unit_profile = self.unit_user.profile
        self.unit_profile.role = UserProfile.Role.DEPOT_ADMIN
        self.unit_profile.save()
        self.unit_profile.assigned_locations.add(self.location)

        self.vendor = Vendor.objects.create(
            name="Cisco Systems Bangladesh",
            category="HARDWARE_OEM",
            status="ACTIVE"
        )

    def test_unauthenticated_user_redirected(self):
        """Unauthenticated user accessing vendor list gets redirected to login."""
        response = self.client.get(reverse('vendor_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_can_view_and_create_vendor(self):
        """Admin can access vendor directory and create a new vendor."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('vendor_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cisco Systems Bangladesh")

        # Create new vendor
        post_data = {
            'name': 'Dell Technologies BD',
            'category': 'HARDWARE_OEM',
            'status': 'ACTIVE',
            'email': 'dell@akij.net',
            'phone': '01800000000',
            'country': 'Bangladesh',
            'credit_period_days': 45,
        }
        create_res = self.client.post(reverse('vendor_create'), data=post_data)
        self.assertEqual(create_res.status_code, 302)
        self.assertTrue(Vendor.objects.filter(name='Dell Technologies BD').exists())

    def test_vendor_contact_addition(self):
        """Test adding a key contact person to a vendor."""
        self.client.force_login(self.admin_user)
        contact_data = {
            'name': 'John Doe',
            'designation': 'Key Account Manager',
            'contact_type': 'SALES',
            'email': 'john@cisco.com',
            'mobile': '01711111111',
            'is_primary': True,
        }
        res = self.client.post(reverse('vendor_contact_add', kwargs={'vendor_pk': self.vendor.pk}), data=contact_data)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(VendorContact.objects.filter(vendor=self.vendor, name='John Doe', is_primary=True).exists())

    def test_rma_claim_logging(self):
        """Test logging an RMA warranty claim."""
        self.client.force_login(self.unit_user)
        rma_data = {
            'vendor': self.vendor.pk,
            'asset': self.asset.pk,
            'location': self.location.pk,
            'issue_description': 'Power Supply Unit failure during surge',
            'dispatch_date': date.today(),
            'status': 'DISPATCHED',
            'standby_provided': False,
        }
        res = self.client.post(reverse('rma_create'), data=rma_data)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(VendorRMA.objects.filter(asset=self.asset, vendor=self.vendor).exists())

    def test_export_vendors_excel(self):
        """Test vendor excel report export."""
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse('export_vendors_excel'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
