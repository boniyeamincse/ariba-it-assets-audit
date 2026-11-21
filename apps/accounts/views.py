from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
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
    Enterprise Authentication Login View with Email & Username Support and Activity Logging.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if not next_url.startswith('/') or not url_has_allowed_host_and_scheme(
        next_url, {request.get_host()}, request.is_secure()
    ):
        next_url = 'home' if request_preferences(request)['default_landing_page'] != 'dashboard' else 'dashboard'

    if request.method == 'POST':
        login_identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not login_identifier or not password:
            messages.error(request, "Please enter both email and password.")
            return render(request, 'accounts/login.html', {'next': next_url, 'username': login_identifier})

        config = request_preferences(request)

        # Allow sign in with Corporate Email or Username
        matched_user = User.objects.filter(
            Q(email__iexact=login_identifier) | Q(username__iexact=login_identifier)
        ).first()

        throttle_key_name = matched_user.username if matched_user else login_identifier
        key = attempt_key(throttle_key_name)
        limit = config['max_login_attempts']
        if login_blocked(key, limit):
            messages.error(request, 'Sign-in is temporarily locked. Please try again later.')
            return render(request, 'accounts/login.html', {'next': next_url, 'username': login_identifier}, status=429)

        auth_username = matched_user.username if matched_user else login_identifier
        user = authenticate(request, username=auth_username, password=password)
        if user is not None and user.is_active:
            if config.get('maintenance_mode') and not user.is_superuser:
                return render(request, 'administration/maintenance.html', status=503)
            if limit:
                LoginThrottle.objects.filter(pk=key).delete()
            login(request, user)
            request.session.set_expiry(config['session_minutes'] * 60)
            if config['log_login_events']:
                log_activity(request, 'LOGIN_SUCCESS', 'Authentication', f"User '{user.username}' ({user.email or 'no email'}) signed in.")
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect(next_url)

        if limit:
            record_failed_login(key, config['lockout_minutes'])
        if config['log_login_events']:
            log_activity(request, 'LOGIN_FAILED', 'Authentication', f"Failed login attempt for email/username: '{login_identifier}'.")
        messages.error(request, 'Invalid email or password.')

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
