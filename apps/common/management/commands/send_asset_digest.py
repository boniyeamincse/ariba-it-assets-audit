from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.models import SystemActivityLog, SystemSettings
from apps.common.preferences import preferences
from apps.devices.models import PendingAssetNotice


class Command(BaseCommand):
    help = 'Send pending asset notifications on the configured daily or weekly cadence.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview the number of notifications without sending.')

    @transaction.atomic
    def handle(self, *args, **options):
        config, _ = SystemSettings.objects.select_for_update().get_or_create(pk=1)
        prefs = preferences(config)
        if not prefs.get('email_notifications'):
            self.stdout.write('Email notifications are disabled.')
            return
        frequency = prefs['notification_frequency']
        today = timezone.localdate(timezone=ZoneInfo(prefs['timezone']))
        if frequency == 'weekly':
            today -= timedelta(days=today.weekday())
        period = f'{frequency}:{today.isoformat()}'
        if config.options.get('last_asset_digest') == period:
            self.stdout.write('This period’s digest has already been sent.')
            return

        if frequency == 'immediate':
            self.stdout.write('Digest delivery is disabled for On event frequency.')
            return

        notices = list(PendingAssetNotice.objects.order_by('created_at', 'pk'))
        if options['dry_run'] or not notices:
            self.stdout.write(f'{len(notices)} pending asset notifications.')
            return
        recipients = prefs.get('notification_recipients', '').splitlines()
        if not recipients:
            raise CommandError('Configure recipients before sending a digest.')
        summary = '\n\n'.join(f'{notice.subject}\n{notice.body}' for notice in notices)
        if not send_mail('Asset activity digest', summary, None, recipients):
            raise CommandError('Email delivery failed.')
        config.options['last_asset_digest'] = period
        config.save(update_fields=['options'])
        PendingAssetNotice.objects.filter(pk__in=[notice.pk for notice in notices]).delete()
        SystemActivityLog.objects.create(
            action='ASSET_DIGEST_SENT', module='Notifications', description=f'Digest sent with {len(notices)} events.',
        )
