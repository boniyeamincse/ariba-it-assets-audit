from ipaddress import ip_address, ip_network
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone, translation

from apps.common.preferences import request_preferences


def address_allowed(address, configured_networks):
    try:
        client = ip_address(address)
    except (TypeError, ValueError):
        return False
    return any(client in ip_network(network) for network in configured_networks.splitlines())


def system_policy(get_response):
    def middleware(request):
        if any(request.path.startswith(prefix) for prefix in (settings.STATIC_URL, settings.MEDIA_URL)):
            return get_response(request)
        preferences = request_preferences(request)
        networks = preferences.get('allowed_ip_addresses')
        if networks and not address_allowed(request.META.get('REMOTE_ADDR'), networks):
            return HttpResponseForbidden('This network is outside the application access policy.')
        with timezone.override(ZoneInfo(preferences['timezone'])), translation.override(preferences['language']):
            if preferences.get('maintenance_mode') and not request.user.is_superuser:
                if request.path not in (reverse('login'), reverse('logout'), reverse('admin:login')):
                    return render(request, 'administration/maintenance.html', status=503)
            return get_response(request)
    return middleware
