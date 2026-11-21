from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import Resolver404, resolve

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
