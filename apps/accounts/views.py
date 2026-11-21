from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.utils.http import url_has_allowed_host_and_scheme
from apps.accounts.logins import attempt_key, login_blocked, record_failed_login
from apps.accounts.models import LoginThrottle
from apps.common.preferences import request_preferences
from apps.common.utils import log_activity

@csrf_protect
def login_view(request):
    """
    Enterprise Authentication Login View with Activity Logging.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if not next_url.startswith('/') or not url_has_allowed_host_and_scheme(
        next_url, {request.get_host()}, request.is_secure()
    ):
        next_url = 'home' if request_preferences(request)['default_landing_page'] != 'dashboard' else 'dashboard'

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'accounts/login.html', {'next': next_url, 'username': username})

        config = request_preferences(request)
        key = attempt_key(username)
        limit = config['max_login_attempts']
        if login_blocked(key, limit):
            messages.error(request, 'Sign-in is temporarily locked. Please try again later.')
            return render(request, 'accounts/login.html', {'next': next_url, 'username': username}, status=429)

        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            if config.get('maintenance_mode') and not user.is_superuser:
                return render(request, 'administration/maintenance.html', status=503)
            if limit:
                LoginThrottle.objects.filter(pk=key).delete()
            login(request, user)
            request.session.set_expiry(config['session_minutes'] * 60)
            if config['log_login_events']:
                log_activity(request, 'LOGIN_SUCCESS', 'Authentication', f"User '{user.username}' signed in.")
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect(next_url)

        if limit:
            record_failed_login(key, config['lockout_minutes'])
        if config['log_login_events']:
            log_activity(request, 'LOGIN_FAILED', 'Authentication', f"Failed login attempt for username: '{username}'.")
        messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html', {'next': next_url})


def logout_view(request):
    """
    Logout view supporting both GET and POST requests.
    """
    username = request.user.username if request.user.is_authenticated else "User"
    if request_preferences(request)['log_login_events']:
        log_activity(request, 'LOGOUT', 'Authentication', f"User '{username}' signed out.")
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


@login_required
def profile_view(request):
    """
    User Profile View.
    """
    return render(request, 'accounts/profile.html', {'user': request.user})
