from datetime import timedelta
from io import BytesIO
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import openpyxl

from apps.accounts.access import Role
from apps.devices.models import DeviceCategory, DeviceType, Asset
from apps.locations.models import Company, Location
from apps.audits.models import AuditSession, AuditItem
from apps.domains.models import DomainRecord


class ReportsModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='Akij Test Subsidiary', short_code='ATS')
        cls.location = Location.objects.create(
            company=cls.company,
            name='Test Factory Site',
            location_id='TFS-01',
            location_type='FACTORY'
        )

        cls.super_admin = User.objects.create_superuser('reports-super', password='SuperPassword123!')
        cls.super_admin.profile.role = Role.SUPER_ADMIN
        cls.super_admin.profile.save()

        cls.depot_user = User.objects.create_user('reports-depot', password='DepotPassword123!')
        cls.depot_user.profile.role = Role.DEPOT_ADMIN
        cls.depot_user.profile.save()

        cls.category = DeviceCategory.objects.create(name='Computing Devices', order=1)
        cls.device_type = DeviceType.objects.create(category=cls.category, name='Desktop Workstation', order=1)

        today = timezone.now().date()

        # Hardware asset
        cls.physical_asset = Asset.objects.create(
            location=cls.location,
            device_type=cls.device_type,
            asset_tag='AST-TFS-0001',
            asset_nature='PHYSICAL',
            status='IN_USE',
            brand='Dell',
            model_name='OptiPlex 7090',
            warranty_expiry=today + timedelta(days=60),
        )

        # Software asset (logical)
        cls.software_asset = Asset.objects.create(
            location=cls.location,
            device_type=cls.device_type,
            asset_tag='SFT-TFS-0001',
            asset_nature='LOGICAL',
            status='IN_USE',
            compliance_status='CRACKED_PIRATED',
            brand='Adobe Master Collection',
            model_name='CC 2022 Cracked',
            seats_purchased=1,
        )

        # Domain record
        cls.domain = DomainRecord.objects.create(
            domain_name='test-report-akij.com',
            company=cls.company,
            category='CORPORATE_PRIMARY',
            registrar='GODADDY',
            expiry_date=today + timedelta(days=45),
            ssl_status='ACTIVE',
            status='ACTIVE',
        )

        # Audit session
        cls.audit_session = AuditSession.objects.create(
            location=cls.location,
            auditor_name='Audit Officer',
            audit_date=today,
            status='APPROVED',
        )
        cls.audit_item = AuditItem.objects.create(
            audit_session=cls.audit_session,
            device_type=cls.device_type,
            active_qty=5,
            backup_qty=2,
            total_qty=7,
        )

    def test_report_hub_view(self):
        """Report Hub should render executive KPIs and report streams."""
        self.client.force_login(self.super_admin)
        res = self.client.get(reverse('report_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Report Center')
        self.assertContains(res, 'Asset Inventory &amp; Lifecycle Report')
        self.assertContains(res, 'Software Compliance &amp; Risk Audit')
        self.assertContains(res, 'Domains, DNS &amp; SSL Governance')
        self.assertContains(res, 'Physical Stock Audit Reconciliation')

    def test_report_asset_inventory_view_and_export(self):
        """Asset inventory report renders table and exports styled Excel."""
        self.client.force_login(self.super_admin)
        url = reverse('report_asset_inventory')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'AST-TFS-0001')
        self.assertContains(res, 'Test Factory Site')

        # Test filter by status
        filtered_res = self.client.get(url, {'status': 'IN_USE'})
        self.assertEqual(filtered_res.status_code, 200)
        self.assertContains(filtered_res, 'AST-TFS-0001')

        # Excel export
        excel_res = self.client.get(reverse('report_asset_excel'))
        self.assertEqual(excel_res.status_code, 200)
        self.assertEqual(
            excel_res['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        wb = openpyxl.load_workbook(BytesIO(excel_res.content))
        self.assertIn("Asset_Inventory_Report", wb.sheetnames)

    def test_report_software_compliance_view_and_export(self):
        """Software compliance report highlights piracy and exports to Excel."""
        self.client.force_login(self.super_admin)
        url = reverse('report_software_compliance')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'SFT-TFS-0001')
        self.assertContains(res, 'Adobe Master Collection')
        self.assertContains(res, 'Cracked / Pirated')

        # Excel export
        excel_res = self.client.get(reverse('report_software_excel'))
        self.assertEqual(excel_res.status_code, 200)
        wb = openpyxl.load_workbook(BytesIO(excel_res.content))
        self.assertIn("Software_Compliance_Audit", wb.sheetnames)

    def test_report_domains_ssl_view_and_export(self):
        """Corporate domain report is accessible by central admins, forbidden for depot users."""
        self.client.force_login(self.super_admin)
        url = reverse('report_domains_ssl')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'test-report-akij.com')

        # Excel export
        excel_res = self.client.get(reverse('report_domains_excel'))
        self.assertEqual(excel_res.status_code, 200)
        wb = openpyxl.load_workbook(BytesIO(excel_res.content))
        self.assertIn("Domain_SSL_Governance", wb.sheetnames)

        # Non-central role blocked
        self.client.force_login(self.depot_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('report_domains_excel')).status_code, 403)

    def test_report_audit_reconciliation_view_and_export(self):
        """Reconciliation report computes variance between physical and system counts."""
        self.client.force_login(self.super_admin)
        url = reverse('report_audit_reconciliation')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Test Factory Site')
        # Counted is 7, physical assets is 1 -> variance is +6
        self.assertContains(res, '+6')

        # Excel export
        excel_res = self.client.get(reverse('report_audit_excel'))
        self.assertEqual(excel_res.status_code, 200)
        wb = openpyxl.load_workbook(BytesIO(excel_res.content))
        self.assertIn("Audit_Reconciliation", wb.sheetnames)
