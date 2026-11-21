from datetime import timedelta
from hashlib import sha256

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import LoginThrottle


def attempt_key(username):
    return sha256(username.casefold().encode()).hexdigest()


def login_blocked(key, limit):
    return bool(limit and LoginThrottle.objects.filter(pk=key, failures__gte=limit, expires_at__gt=timezone.now()).exists())


@transaction.atomic
def record_failed_login(key, minutes):
    now = timezone.now()
    expires = now + timedelta(minutes=minutes)
    attempt, _ = LoginThrottle.objects.select_for_update().get_or_create(pk=key, defaults={'expires_at': expires})
    if attempt.expires_at <= now:
        attempt.failures = 0
    attempt.failures += 1
    attempt.expires_at = expires
    attempt.save(update_fields=['failures', 'expires_at'])
