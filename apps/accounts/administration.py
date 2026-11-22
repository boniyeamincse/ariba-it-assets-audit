from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_safe, require_http_methods

from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, LOCAL_TYPES, Role, role_for, roles_required
from apps.accounts.forms import ManagedUserForm, RoleDefinitionForm, UserFilterForm
from apps.accounts.models import RoleDefinition
from apps.accounts.navigation import portal_navigation
from apps.accounts.settings_forms import CATEGORIES, CORE_FIELDS, SECTION_METADATA, SectionSettingsForm
from apps.common.models import SystemSettings
from apps.common.middleware import address_allowed
from apps.common.utils import log_activity
from apps.common.preferences import preferences, request_preferences
from apps.devices.configuration import example_asset_tag


def navigation(request):
    role = role_for(request.user)
    label = Role(role).label if role else ''
    if role in (Role.HO_ADMIN, *LOCAL_TYPES) and request.user.profile.custom_role_id:
        label = request.user.profile.role_label
    return {
        'portal': request_preferences(request),
        'can_administrate': role in CENTRAL_ROLES,
        'has_operational_access': role in DASHBOARD_ROUTES,
        'administration_role': label,
        **portal_navigation(request, role),
    }


def managed_users(actor):
    users = User.objects.filter(is_superuser=False)
    if role_for(actor) == Role.HO_ADMIN:
        users = users.filter(is_staff=False).filter(
            Q(profile__role__in=(*LOCAL_TYPES, Role.PENDING)) | Q(profile__isnull=True)
        ).exclude(profile__custom_role__base_role=Role.HO_ADMIN)
    return users


@login_required
@require_safe
def dashboard_entry(request):
    role = role_for(request.user)
    route = DASHBOARD_ROUTES.get(role)
    if route:
        config = request_preferences(request)
        landing = config['default_landing_page']
        if landing in ('assets', 'audits') and request.path == '/':
            return redirect({'assets': 'asset_list', 'audits': 'audit_list'}[landing])
        if config['default_dashboard'] == 'matrix':
            return redirect('matrix')
        return redirect(route)
    return render(request, 'administration/pending.html', {'support_email': SystemSettings.current().support_email}, status=403)


@roles_required(*CENTRAL_ROLES)
@require_safe
def user_list(request):
    base_users = managed_users(request.user)
    users = base_users.select_related('profile__custom_role').prefetch_related('profile__assigned_locations')
    filters = UserFilterForm(request.GET, actor_role=role_for(request.user))
    if filters.is_valid():
        query, role, status, location = (filters.cleaned_data[key] for key in ('q', 'role', 'status', 'location'))
        if query:
            users = users.filter(
                Q(username__icontains=query) | Q(first_name__icontains=query) |
                Q(last_name__icontains=query) | Q(email__icontains=query) | Q(profile__designation__icontains=query)
            )
        if role == Role.PENDING:
            users = users.filter(Q(profile__role=role) | Q(profile__isnull=True))
        elif role:
            base_role, custom_role, _ = filters.role_options[role]
            users = users.filter(profile__role=base_role, profile__custom_role=custom_role)
        if status:
            users = users.filter(is_active=status == 'active')
        if location:
            users = users.filter(profile__assigned_locations=location)
    else:
        users = users.none()
    page = Paginator(users.order_by('username'), SystemSettings.current().user_page_size).get_page(request.GET.get('page'))
    stats = {
        'total': base_users.count(),
        'active': base_users.filter(is_active=True).count(),
        'inactive': base_users.filter(is_active=False).count(),
        'ho_count': base_users.filter(profile__role=Role.HO_ADMIN).count(),
        'local_count': base_users.filter(profile__role__in=LOCAL_TYPES).count(),
        'pending_count': base_users.filter(Q(profile__role=Role.PENDING) | Q(profile__isnull=True)).count(),
    }
    return render(request, 'administration/users.html', {'page_obj': page, 'filters': filters, 'stats': stats})


@roles_required(*CENTRAL_ROLES)
@require_http_methods(['GET', 'HEAD', 'POST'])
@transaction.atomic
def user_editor(request, user_id=None):
    account = None
    if user_id is not None:
        users = managed_users(request.user).exclude(pk=request.user.pk)
        account = get_object_or_404(users, pk=user_id)
        if request.method == 'POST':
            get_object_or_404(User.objects.select_for_update(), pk=account.pk)
            account = get_object_or_404(users, pk=account.pk)
    form = ManagedUserForm(
        request.POST if request.method == 'POST' else None,
        actor_role=role_for(request.user), instance=account,
    )
    if request.method == 'POST' and form.is_valid():
        user = form.save_account()
        action = 'UPDATE_USER' if account else 'CREATE_USER'
        description = (
            f'Account #{user.pk} ({user.username}) saved. '
            f'Role: {user.profile.role_label}. Active: {user.is_active}. '
            f'Locations: {", ".join(user.profile.assigned_locations.values_list("code", flat=True)) or "none"}.'
        )
        log_activity(request, action, 'Administration', description)
        messages.success(request, f'Account {user.username} saved.')
        return redirect('administration_users')
    return render(request, 'administration/user_form.html', {'form': form, 'account': account})


@roles_required(*CENTRAL_ROLES)
@require_safe
def roles_view(request):
    roles = RoleDefinition.objects.filter(is_active=True).annotate(member_count=Count('profiles'))
    return render(request, 'administration/roles.html', {'custom_roles': roles})


@roles_required(Role.SUPER_ADMIN)
@require_http_methods(['GET', 'HEAD', 'POST'])
def role_create(request):
    form = RoleDefinitionForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                role = form.save()
                log_activity(request, 'CREATE_ROLE', 'Administration',
                             f'Created role {role.name} ({role.get_base_role_display()}).')
        except IntegrityError:
            if not RoleDefinition.objects.filter(name__iexact=form.cleaned_data['name']).exists():
                raise
            form.add_error('name', 'This role name is already in use.')
        else:
            messages.success(request, f'Role “{role.name}” added.')
            return redirect('administration_roles')
    return render(request, 'administration/role_form.html', {'form': form})


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ['session_minutes', 'activity_page_size', 'user_page_size', 'support_email']
        labels = {
            'session_minutes': 'Session duration (minutes)',
            'activity_page_size': 'Activity logs per page',
            'user_page_size': 'Users per page',
            'support_email': 'IT support email',
        }
        help_texts = {
            'session_minutes': 'Applies when a user next signs in.',
            'support_email': 'Shown to users who are waiting for a role assignment.',
        }

    @property
    def sections(self):
        return (
            ('Sign-in', (self['session_minutes'],)),
            ('List display', (self['user_page_size'], self['activity_page_size'])),
            ('Support contact', (self['support_email'],)),
        )


def get_asset_stats():
    from apps.devices.models import DeviceCategory, DeviceType, Asset
    from django.db.models import Count
    categories_data = list(DeviceCategory.objects.annotate(
        type_cnt=Count('devices', distinct=True),
        asset_cnt=Count('devices__assets', distinct=True)
    ).order_by('order', 'name'))
    return {
        'categories_count': len(categories_data),
        'types_count': DeviceType.objects.count(),
        'total_assets': Asset.objects.count(),
        'categories': categories_data,
        'status_counts': {
            'IN_USE': Asset.objects.filter(status='IN_USE').count(),
            'BACKUP': Asset.objects.filter(status='BACKUP').count(),
            'FAULTY': Asset.objects.filter(status='FAULTY').count(),
            'SCRAP': Asset.objects.filter(status='SCRAP').count(),
        },
    }


@roles_required(*CENTRAL_ROLES)
@require_http_methods(['GET', 'HEAD', 'POST'])
@transaction.atomic
def settings_view(request, section=None):
    editable = role_for(request.user) == Role.SUPER_ADMIN
    if request.method == 'POST' and not editable:
        raise PermissionDenied
    selected = section or 'general'
    if selected not in CATEGORIES:
        raise Http404

    if request.method == 'POST':
        config, _ = SystemSettings.objects.select_for_update().get_or_create(pk=1)
    else:
        config = SystemSettings.current()

    if request.method == 'POST' and section is None and 'session_minutes' in request.POST:
        data = request.POST.copy()
        data.setdefault('user_page_size', config.user_page_size)
        data.setdefault('support_email', config.support_email)
        form = SystemSettingsForm(data, instance=config)
    else:
        form = SectionSettingsForm(
            request.POST if request.method == 'POST' else None,
            section=selected, config=config, editable=editable,
        )

    context = {
        'form': form, 'editable': editable, 'sections': CATEGORIES,
        'section_metadata': SECTION_METADATA, 'selected': selected,
        'section_title': CATEGORIES[selected],
        'current_meta': SECTION_METADATA.get(selected, {}),
    }
    if selected == 'assets':
        context['asset_stats'] = get_asset_stats()
    elif selected == 'asset-id':
        context['asset_id_preview'] = example_asset_tag(preferences(config))

    if request.method == 'POST' and form.is_valid():
        changed = form.changed_data
        networks = form.cleaned_data.get('allowed_ip_addresses')
        if networks and not address_allowed(request.META.get('REMOTE_ADDR'), networks):
            form.add_error('allowed_ip_addresses', 'Include your current network before saving this policy.')
            changed = ()
        if form.errors:
            return render(request, 'administration/settings.html', context)
        for name in changed:
            value = form.cleaned_data[name]
            if name in CORE_FIELDS:
                setattr(config, name, value)
            else:
                config.options[name] = value
        if changed:
            config.save()
            labels = ', '.join(str(getattr(form.fields.get(name), 'label', None) or name) for name in changed)
            log_activity(request, 'UPDATE_SYSTEM_SETTINGS', 'Administration', f'Updated settings: {labels}.')
        messages.success(request, 'System settings saved.')
        if section is None:
            return redirect('administration_settings')
        return redirect('administration_settings_section', section=selected)

    return render(request, 'administration/settings.html', context)


@roles_required(*CENTRAL_ROLES)
@require_safe
def asset_id_preview(request):
    config = SystemSettings.current()
    if request.GET:
        form = SectionSettingsForm(request.GET, section='asset-id', config=config, editable=True)
        if not form.is_valid():
            return JsonResponse({'valid': False}, status=400)
        return JsonResponse({'tag': example_asset_tag(form.cleaned_data)})
    return JsonResponse({'tag': example_asset_tag(preferences(config))})
