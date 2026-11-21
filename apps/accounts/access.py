from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps

from apps.accounts.models import UserProfile
from apps.locations.models import Location

Role = UserProfile.Role
LOCAL_TYPES = {Role.FACTORY_ADMIN: 'FACTORY', Role.DEPOT_ADMIN: 'DEPOT'}
CENTRAL_ROLES = (Role.SUPER_ADMIN, Role.HO_ADMIN)
DASHBOARD_ROUTES = {
    Role.SUPER_ADMIN: 'super_dashboard',
    Role.HO_ADMIN: 'ho_dashboard',
    Role.FACTORY_ADMIN: 'factory_dashboard',
    Role.DEPOT_ADMIN: 'depot_dashboard',
}


def role_for(user):
    if not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser:
        return Role.SUPER_ADMIN
    profile = getattr(user, 'profile', None)
    if profile and profile.is_active:
        base_role = profile.custom_role.base_role if profile.custom_role_id else profile.role
        if base_role in (Role.HO_ADMIN, *LOCAL_TYPES):
            return base_role
    return Role.PENDING


def roles_required(*roles):
    def decorate(view):
        @login_required
        @wraps(view)
        def checked(request, *args, **kwargs):
            if role_for(request.user) not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return checked

    return decorate


def visible_locations(user):
    role = role_for(user)
    if role in CENTRAL_ROLES:
        return Location.objects.all()
    if role in LOCAL_TYPES:
        return user.profile.assigned_locations.filter(location_type=LOCAL_TYPES[role])
    return Location.objects.none()
