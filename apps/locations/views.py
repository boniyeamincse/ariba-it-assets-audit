from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, roles_required, visible_locations
from apps.audits.models import AuditSession
from apps.common.preferences import request_preferences
from apps.common.utils import log_activity
from apps.locations.forms import LocationForm
from apps.locations.models import Company, Location


class LocationFilters(forms.Form):
    q = forms.CharField(
        label='Search', required=False, max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Name, code, city or contact'}),
    )
    type = forms.ChoiceField(label='Type', required=False, choices=[('', 'All types'), *Location.LOCATION_TYPES])
    status = forms.ChoiceField(label='Status', required=False, choices=[('', 'All statuses'), ('active', 'Active'), ('inactive', 'Inactive')])
    company = forms.ModelChoiceField(queryset=Company.objects.none(), empty_label='All companies', required=False)


@roles_required(*DASHBOARD_ROUTES)
@require_safe
def location_list_view(request):
    visible = visible_locations(request.user)
    approved = AuditSession.objects.filter(location_id=OuterRef('pk'), status='APPROVED')
    summary = visible.aggregate(
        total=Count('pk'),
        active=Count('pk', filter=Q(is_active=True)),
        audited=Count('pk', filter=Exists(approved)),
    )
    filters = LocationFilters(request.GET)
    filters.fields['company'].queryset = Company.objects.filter(pk__in=visible.values('company_id')).order_by('name')
    locations = visible
    if filters.is_valid():
        search, loc_type, status, company = (filters.cleaned_data[name] for name in ('q', 'type', 'status', 'company'))
        if search:
            locations = locations.filter(
                Q(name__icontains=search) | Q(code__icontains=search) | Q(location_id__icontains=search) |
                Q(city__icontains=search) | Q(division__icontains=search) | Q(contact_person__icontains=search)
            )
        if loc_type:
            locations = locations.filter(location_type=loc_type)
        if status:
            locations = locations.filter(is_active=status == 'active')
        if company:
            locations = locations.filter(company=company)
    else:
        locations = locations.none()

    latest = approved.order_by('-audit_date', '-pk')
    page = Paginator(locations.select_related('company', 'parent_location').annotate(
        tracked_assets=Count('assets'),
        latest_audit_id=Subquery(latest.values('pk')[:1]),
        latest_audit_date=Subquery(latest.values('audit_date')[:1]),
        audited_quantity=Subquery(latest.annotate(quantity=Sum('items__total_qty', default=0)).values('quantity')[:1]),
    ).order_by('name', 'pk'), 25).get_page(request.GET.get('page'))

    type_counts = {item['location_type']: item['count'] for item in visible.values('location_type').annotate(count=Count('pk'))}

    return render(request, 'locations/location_list.html', {
        'page_obj': page,
        'filters': filters,
        'has_filters': any(filters[name].value() for name in filters.fields),
        'summary': summary,
        'inactive_count': summary['total'] - summary['active'],
        'type_counts': type_counts,
        'current_type': request.GET.get('type', ''),
    })


@roles_required(*DASHBOARD_ROUTES)
@require_safe
def location_detail_view(request, loc_id):
    """
    Detailed 360-degree technical profile of a location including assets, audit history, and personnel.
    """
    visible = visible_locations(request.user)
    location = get_object_or_404(visible.select_related('company', 'parent_location'), pk=loc_id)
    
    # Tracked assets at this location
    assets = location.assets.select_related('device_type__category', 'owning_company').order_by('-created_at')
    total_assets = assets.count()
    active_assets = assets.filter(is_active=True).count()
    
    # Audit history
    audits = location.audit_sessions.order_by('-audit_date')
    total_audits = audits.count()
    latest_audit = audits.first()
    
    # Sub-locations / Annexes
    sub_locations = location.sub_locations.select_related('company').all()
    
    # User profiles assigned
    assigned_users = location.assigned_profiles.select_related('user').all()

    return render(request, 'locations/location_detail.html', {
        'location': location,
        'assets': assets[:20],
        'total_assets': total_assets,
        'active_assets': active_assets,
        'audits': audits,
        'total_audits': total_audits,
        'latest_audit': latest_audit,
        'sub_locations': sub_locations,
        'assigned_users': assigned_users,
    })


@roles_required(*CENTRAL_ROLES)
@require_http_methods(['GET', 'HEAD', 'POST'])
def location_create_or_edit_view(request, loc_id=None):
    location = get_object_or_404(Location.objects.select_related('company'), pk=loc_id) if loc_id else None
    config = request_preferences(request)
    active_companies = Company.objects.filter(is_active=True).order_by('name')
    default_company = (
        location.company if location else
        active_companies.filter(pk=config.get('default_company')).first() or active_companies.first()
    )
    form = LocationForm(
        request.POST if request.method == 'POST' else None,
        instance=location,
        default_company=default_company,
    )
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if location:
                    Company.objects.select_for_update().get(pk=location.company_id)
                if form.is_valid():
                    saved = form.save(commit=False)
                    if not saved.company_id:
                        saved.company, _ = Company.objects.get_or_create(
                            short_code=config.get('company_code_prefix') or 'AKIJ',
                            defaults={'name': config.get('group_name') or config['organization_name']},
                        )
                    saved.is_active = (form.cleaned_data['status'] or form.initial['status']) == 'ACTIVE'
                    saved.save()
                    log_activity(
                        request, 'UPDATE_LOCATION' if location else 'CREATE_LOCATION', 'Locations',
                        f"Saved location [{saved.location_id}] '{saved.name}' ({saved.code}).",
                    )
                    messages.success(request, f'Location “{saved.name}” saved successfully.')
                    return redirect('location_list')
        except IntegrityError:
            form.add_error(None, 'The location code or ID was saved by another request. Check the values and try again.')

    return render(request, 'locations/location_form.html', {'location': location, 'form': form})


@roles_required(*CENTRAL_ROLES)
def location_delete_view(request, loc_id):
    """
    Safely delete or deactivate a location record with dependency integrity verification.
    """
    location = get_object_or_404(Location.objects.select_related('company'), pk=loc_id)
    asset_count = location.assets.count()
    audit_count = location.audit_sessions.count()
    sub_count = location.sub_locations.count()
    has_dependencies = (asset_count > 0 or audit_count > 0 or sub_count > 0)

    if request.method == 'POST':
        action = request.POST.get('action', 'delete')
        if action == 'deactivate':
            location.is_active = False
            location.save()
            log_activity(
                request,
                'DEACTIVATE_LOCATION',
                'Locations',
                f"Deactivated location [{location.location_id}] '{location.name}'."
            )
            messages.success(request, f"Location '{location.name}' has been deactivated.")
            return redirect('location_list')

        if has_dependencies:
            messages.error(
                request,
                f"Cannot delete location '{location.name}' because it contains "
                f"{asset_count} tracked asset(s), {audit_count} audit session(s), and {sub_count} sub-location(s). "
                f"Please reassign or delete them first, or deactivate this location."
            )
            return redirect('location_edit', loc_id=location.id)

        loc_name = location.name
        loc_id_str = location.location_id or f"ID-{location.id}"
        location.delete()
        log_activity(
            request,
            'DELETE_LOCATION',
            'Locations',
            f"Deleted location [{loc_id_str}] '{loc_name}'."
        )
        messages.success(request, f"Location '{loc_name}' has been permanently deleted.")
        return redirect('location_list')

    return render(request, 'locations/location_confirm_delete.html', {
        'location': location,
        'asset_count': asset_count,
        'audit_count': audit_count,
        'sub_count': sub_count,
        'has_dependencies': has_dependencies,
    })
