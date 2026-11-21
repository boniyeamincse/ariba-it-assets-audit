from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.models import SystemActivityLog, SystemSettings
from apps.common.preferences import preferences
from apps.devices.models import Asset


class Command(BaseCommand):
    help = 'Send one weekly summary of active assets with a warranty expiring in the next 30 days.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show the number of due assets without sending email.')

    @transaction.atomic
    def handle(self, *args, **options):
        config, _ = SystemSettings.objects.select_for_update().get_or_create(pk=1)
        prefs = preferences(config)
        if not prefs.get('email_notifications') or not prefs.get('notify_warranty_expiry'):
            self.stdout.write('Warranty notifications are disabled.')
            return
        recipients = prefs.get('notification_recipients', '').splitlines()
        if not recipients:
            raise CommandError('Configure notification recipients before enabling warranty alerts.')
        today = timezone.localdate(timezone=ZoneInfo(prefs['timezone']))
        week = today - timedelta(days=today.weekday())
        if config.options.get('last_warranty_notice_week') == week.isoformat():
            self.stdout.write('This week’s warranty alert has already been sent.')
            return
        assets = list(Asset.objects.filter(
            is_active=True, warranty_expiry__range=(today, today + timedelta(days=30)),
        ).order_by('warranty_expiry', 'asset_tag').values_list('asset_tag', 'warranty_expiry'))
        if options['dry_run'] or not assets:
            self.stdout.write(f'{len(assets)} warranties are due within 30 days.')
            return
        body = '\n'.join(f'{tag}: {expiry.isoformat()}' for tag, expiry in assets)
        if not send_mail('Asset warranties expiring within 30 days', body, None, recipients):
            raise CommandError('Email delivery failed.')
        config.options['last_warranty_notice_week'] = week.isoformat()
        config.save(update_fields=['options'])
        SystemActivityLog.objects.create(
            action='WARRANTY_ALERT_SENT', module='Notifications', description=f'Warranty alert sent for {len(assets)} assets.',
        )
