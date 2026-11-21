from apps.common.models import SystemActivityLog

def get_client_ip(request):
    """
    Extracts the client's real IP address from HTTP headers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def log_activity(request, action, module, description):
    """
    Records an enterprise audit log event in the database.
    """
    user_name = "Anonymous"
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        user_name = request.user.username

    ip_address = get_client_ip(request) if request else "127.0.0.1"

    return SystemActivityLog.objects.create(
        user_name=user_name,
        action=action,
        module=module,
        description=description,
        ip_address=ip_address
    )
