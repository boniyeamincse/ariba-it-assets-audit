from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.common.models import SystemActivityLog
from apps.common.preferences import preferences


class Command(BaseCommand):
    help = 'Preview or apply the configured activity log retention policy.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Delete the expired entries.')

    def handle(self, *args, **options):
        retention = preferences()['audit_log_retention_days']
        if not retention:
            self.stdout.write('Activity log retention is unlimited.')
            return
        expired = SystemActivityLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=retention))
        if options['apply']:
            count, _ = expired.delete()
            self.stdout.write(f'Deleted {count} expired activity log entries.')
        else:
            self.stdout.write(f'{expired.count()} activity log entries are outside the retention window.')
