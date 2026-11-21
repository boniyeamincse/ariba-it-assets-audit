from functools import partial

from django.core.mail import send_mail
from django.db import transaction

from apps.common.models import SystemActivityLog


def deliver_notification(subject, body, recipients):
    try:
        send_mail(subject, body, None, recipients)
    except (OSError, ValueError):
        SystemActivityLog.objects.create(
            action='EMAIL_DELIVERY_FAILED', module='Notifications',
            description=f'Unable to deliver notification: {subject}.',
        )


def queue_asset_notifications(asset, previous, config):
    if not config.get('email_notifications'):
        return
    recipients = config.get('notification_recipients', '').splitlines()
    if not recipients:
        return
    events = {
        'notify_asset_created': ('New asset created', previous is None),
        'notify_asset_assigned': ('Asset assigned', bool(asset.assigned_user and (previous is None or asset.assigned_user != previous['assigned_user']))),
        'notify_asset_transferred': ('Asset transferred', bool(previous and previous['location_id'] != asset.location_id)),
    }
    for key, (label, occurred) in events.items():
        if occurred and config.get(key):
            subject = f'{label}: {asset.asset_tag}'
            body = f'Asset {asset.asset_tag} is recorded at {asset.location.name}.'
            if config['notification_frequency'] == 'immediate':
                transaction.on_commit(partial(deliver_notification, subject, body, recipients))
            else:
                from apps.devices.models import PendingAssetNotice

                PendingAssetNotice.objects.create(subject=subject, body=body)
