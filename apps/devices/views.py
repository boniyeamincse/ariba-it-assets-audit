from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe
from django.http import Http404, HttpResponse
from django.db.models import Q, Count, Exists, OuterRef, Prefetch
from django.urls import reverse
from datetime import date
from urllib.parse import urlsplit, urlunsplit
import csv
import io

from apps.devices.models import DeviceCategory, DeviceType, Asset
from apps.locations.models import Company, Location
from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, role_for, roles_required, visible_locations
from apps.common.utils import log_activity
from apps.common.preferences import request_preferences
from apps.devices.configuration import ASSET_METADATA, TAG_CATEGORY_CHOICES, asset_status_choices, normalize_asset_tag

@roles_required(*DASHBOARD_ROUTES)
def asset_list_view(request):
    """
    List all physical IT assets with location-wise, category, and status filtering.
    """
    assets_qs = Asset.objects.filter(location__in=visible_locations(request.user)).select_related(
        'device_type', 'device_type__category', 'location'
    )

    # Filters
    loc_filter = request.GET.get('location', '').strip()
    cat_filter = request.GET.get('category', '').strip()
    device_type_filter = request.GET.get('device_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    nature_filter = request.GET.get('nature', '').strip()
    compliance_filter = request.GET.get('compliance', '').strip()
    risk_filter = request.GET.get('risk', '').strip()
    search_query = request.GET.get('q', '').strip()

    if loc_filter:
        assets_qs = assets_qs.filter(location_id=loc_filter)

    if cat_filter:
        assets_qs = assets_qs.filter(device_type__category_id=cat_filter)

    if nature_filter in ('PHYSICAL', 'LOGICAL'):
        assets_qs = assets_qs.filter(asset_nature=nature_filter)

    if compliance_filter:
        assets_qs = assets_qs.filter(compliance_status=compliance_filter)

    if risk_filter:
        assets_qs = assets_qs.filter(risk_level=risk_filter)

    selected_device_type = None
    if device_type_filter:
        try:
            device_type_id = int(device_type_filter)
        except ValueError as error:
            raise Http404('Device type not found.') from error
        selected_device_type = get_object_or_404(DeviceType, pk=device_type_id)
        assets_qs = assets_qs.filter(device_type=selected_device_type)

    if status_filter:
        assets_qs = assets_qs.filter(status=status_filter)

    if search_query:
        assets_qs = assets_qs.filter(
            Q(asset_tag__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(license_key__icontains=search_query) |
            Q(device_type__name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(vendor__icontains=search_query) |
            Q(model_name__icontains=search_query) |
            Q(version__icontains=search_query) |
            Q(assigned_user__icontains=search_query) |
            Q(department__icontains=search_query)
        )

    # Metrics
    total_assets = assets_qs.count()
    in_use_count = assets_qs.filter(status='IN_USE').count()
    backup_count = assets_qs.filter(status='BACKUP').count()
    faulty_count = assets_qs.filter(status__in=['FAULTY', 'SCRAP']).count()

    # Dropdown lists
    locations = visible_locations(request.user).order_by('location_id', 'name')
    categories = DeviceCategory.objects.all().order_by('order')

    # Pagination
    paginator = Paginator(assets_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    status_choices = asset_status_choices(request_preferences(request))
    labels = dict(status_choices)
    for asset in page_obj:
        asset.configured_status_label = labels.get(asset.status, asset.get_status_display())

    context = {
        'page_obj': page_obj,
        'total_assets': total_assets,
        'in_use_count': in_use_count,
        'backup_count': backup_count,
        'faulty_count': faulty_count,
        'locations': locations,
        'categories': categories,
        'loc_filter': loc_filter,
        'cat_filter': cat_filter,
        'nature_filter': nature_filter,
        'compliance_filter': compliance_filter,
        'risk_filter': risk_filter,
        'selected_device_type': selected_device_type,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': status_choices,
        'compliance_choices': Asset.COMPLIANCE_CHOICES,
        'risk_level_choices': Asset.RISK_LEVEL_CHOICES,
    }
    return render(request, 'devices/asset_list.html', context)


@roles_required(*DASHBOARD_ROUTES)
def asset_create_or_edit_view(request, asset_id=None):
    """
    Dynamic Location-Wise Physical & Logical IT Asset Entry & Edit Form.
    """
    asset = None
    if asset_id:
        asset = get_object_or_404(Asset, id=asset_id, location__in=visible_locations(request.user))
        if asset.retired_at:
            if request.method == 'POST':
                raise PermissionDenied('Retired assets cannot be edited.')
            return redirect('asset_detail', asset_id=asset.pk)

    locations = visible_locations(request.user).order_by('location_id', 'name')
    categories = DeviceCategory.objects.prefetch_related('devices').all().order_by('order')
    device_types = DeviceType.objects.select_related('category').all().order_by('category__order', 'name')

    can_set_owner = role_for(request.user) in CENTRAL_ROLES
    owners = Company.objects.filter(is_active=True)
    if asset and asset.owning_company_id:
        owners = Company.objects.filter(Q(is_active=True) | Q(pk=asset.owning_company_id))

    config = request_preferences(request)
    status_choices = asset_status_choices(config)
    metadata_fields = []
    for key, (label, preference) in ASSET_METADATA.items():
        choices = config[preference].splitlines()
        current = getattr(asset, key, '')
        if current and current not in choices:
            choices.append(current)
        metadata_fields.append((key, label, choices, current))

    def form_context():
        initial_nature = request.POST.get('asset_nature') or getattr(asset, 'asset_nature', '') or request.GET.get('nature')
        if not initial_nature and request.GET.get('type') == 'chat':
            initial_nature = 'LOGICAL'
        if initial_nature not in ('PHYSICAL', 'LOGICAL'):
            initial_nature = 'PHYSICAL'

        initial_device_id = request.POST.get('device_type') or request.GET.get('device_type')
        if not initial_device_id and request.GET.get('type') == 'chat':
            chat_dt = DeviceType.objects.filter(name__icontains='chat').first()
            if chat_dt:
                initial_device_id = str(chat_dt.id)

        return {
            'asset': asset, 'locations': locations, 'categories': categories,
            'device_types': device_types, 'status_choices': status_choices,
            'metadata_fields': metadata_fields, 'currency': getattr(asset, 'currency', '') or config['asset_currency'],
            'default_warranty_months': config['default_warranty_months'],
            'nature_choices': Asset.NATURE_CHOICES,
            'current_nature': initial_nature,
            'submitted_device_id': initial_device_id,
            'submitted_location_id': request.POST.get('location'),
            'submitted_tag': request.POST.get('asset_tag', ''),
            'owner_choices': owners if can_set_owner else None,
            'selected_owner': request.POST.get('owning_company') or (
                str(asset.owning_company_id) if asset and asset.owning_company_id else ''
            ),
            'compliance_choices': Asset.COMPLIANCE_CHOICES,
            'risk_level_choices': Asset.RISK_LEVEL_CHOICES,
            'remediation_choices': Asset.REMEDIATION_CHOICES,
            'current_compliance': request.POST.get('compliance_status') or getattr(asset, 'compliance_status', 'GENUINE'),
            'current_risk': request.POST.get('risk_level') or getattr(asset, 'risk_level', 'LOW'),
            'current_remediation': request.POST.get('remediation_plan') or getattr(asset, 'remediation_plan', 'COMPLIANT'),
            'current_seats_purchased': request.POST.get('seats_purchased') or getattr(asset, 'seats_purchased', 1),
            'current_seats_allocated': request.POST.get('seats_allocated') or getattr(asset, 'seats_allocated', 1),
        }

    if request.method == 'POST':
        asset_nature = request.POST.get('asset_nature', 'PHYSICAL').strip()
        if asset_nature not in ('PHYSICAL', 'LOGICAL'):
            asset_nature = 'PHYSICAL'
        asset_tag = normalize_asset_tag(request.POST.get('asset_tag', ''))
        device_type_id = request.POST.get('device_type')
        location_id = request.POST.get('location')
        brand = request.POST.get('brand', '').strip()
        model_name = request.POST.get('model_name', '').strip()
        serial_number = request.POST.get('serial_number', '').strip()
        vendor = request.POST.get('vendor', '').strip()
        version = request.POST.get('version', '').strip()
        license_key = request.POST.get('license_key', '').strip()
        host_server = request.POST.get('host_server', '').strip()
        department = request.POST.get('department', '').strip()
        assigned_user = request.POST.get('assigned_user', '').strip()
        status = request.POST.get('status', 'IN_USE')
        ip_address = request.POST.get('ip_address', '').strip() or None
        mac_address = request.POST.get('mac_address', '').strip() or None
        purchase_date_str = request.POST.get('purchase_date', '').strip()
        warranty_expiry_str = request.POST.get('warranty_expiry', '').strip()
        remarks = request.POST.get('remarks', '').strip()

        compliance_status = request.POST.get('compliance_status', 'GENUINE').strip()
        if compliance_status not in dict(Asset.COMPLIANCE_CHOICES):
            compliance_status = 'GENUINE'

        risk_level = request.POST.get('risk_level', 'LOW').strip()
        if risk_level not in dict(Asset.RISK_LEVEL_CHOICES):
            risk_level = 'LOW'

        remediation_plan = request.POST.get('remediation_plan', 'COMPLIANT').strip()
        if remediation_plan not in dict(Asset.REMEDIATION_CHOICES):
            remediation_plan = 'COMPLIANT'

        try:
            seats_purchased = max(0, int(request.POST.get('seats_purchased', 1) or 1))
        except (ValueError, TypeError):
            seats_purchased = 1

        try:
            seats_allocated = max(0, int(request.POST.get('seats_allocated', 1) or 1))
        except (ValueError, TypeError):
            seats_allocated = 1

        # Security Risk Escalation for cracked or pirated software
        if compliance_status == 'CRACKED_PIRATED':
            if risk_level in ('LOW', 'MEDIUM'):
                risk_level = 'HIGH'
            if remediation_plan == 'COMPLIANT':
                remediation_plan = 'PURCHASE_OFFICIAL'

        if asset_nature == 'LOGICAL':
            if vendor and not brand:
                brand = vendor
            if version and not model_name:
                model_name = version
            if license_key and not serial_number:
                serial_number = license_key

        if not device_type_id or not location_id:
            messages.error(request, "Device Type and Location are required.")
            return render(request, 'devices/asset_form.html', form_context())

        metadata = {}
        for key, label, choices, current in metadata_fields:
            value = request.POST.get(key, current)
            if value and value not in choices:
                messages.error(request, f'Select a valid {label.lower()}.')
                return render(request, 'devices/asset_form.html', form_context(), status=400)
            metadata[key] = value
        if status not in dict(status_choices):
            messages.error(request, 'Select a valid asset status.')
            return render(request, 'devices/asset_form.html', form_context(), status=400)

        dev = get_object_or_404(DeviceType, id=device_type_id)
        loc = get_object_or_404(locations, id=location_id)

        owner_id = request.POST.get('owning_company', '').strip()
        owner = asset.owning_company if asset else None
        if owner_id:
            if not can_set_owner:
                raise PermissionDenied('Only central administrators may change asset ownership.')
            owner = owners.filter(pk=owner_id).first() if owner_id.isdecimal() else None
            if not owner:
                messages.error(request, 'Choose a valid owning company.')
                return render(request, 'devices/asset_form.html', form_context(), status=400)

        purchase_date = date.fromisoformat(purchase_date_str) if purchase_date_str else None
        warranty_expiry = date.fromisoformat(warranty_expiry_str) if warranty_expiry_str else None

        if asset and asset_tag and asset_tag != normalize_asset_tag(asset.asset_tag):
            return render(request, 'devices/asset_form.html', {
                **form_context(), 'asset_tag_error': 'An issued asset tag cannot be changed.',
            }, status=400)

        try:
            is_new = asset is None

            if is_new:
                asset = Asset.objects.create(
                    asset_nature=asset_nature,
                    asset_tag=asset_tag or '',
                    device_type=dev,
                    location=loc,
                    owning_company=owner,
                    brand=brand,
                    model_name=model_name,
                    serial_number=serial_number,
                    vendor=vendor,
                    version=version,
                    license_key=license_key,
                    host_server=host_server,
                    department=department,
                    assigned_user=assigned_user,
                    status=status,
                    ip_address=ip_address,
                    mac_address=mac_address,
                    purchase_date=purchase_date,
                    warranty_expiry=warranty_expiry,
                    compliance_status=compliance_status,
                    risk_level=risk_level,
                    remediation_plan=remediation_plan,
                    seats_purchased=seats_purchased,
                    seats_allocated=seats_allocated,
                    remarks=remarks,
                    **metadata,
                )
                log_activity(
                    request=request,
                    action='CREATE_ASSET',
                    module='Assets',
                    description=f"Added {asset.get_asset_nature_display()} [{asset.asset_tag}] {dev.name} to {loc.name} ({loc.location_id}). Assigned: {assigned_user or 'None'}."
                )
                messages.success(request, f"Asset '{asset.asset_tag}' ({dev.name}) successfully registered at {loc.name}!")
            else:
                asset.asset_nature = asset_nature
                asset.device_type = dev
                asset.location = loc
                if owner:
                    asset.owning_company = owner
                asset.brand = brand
                asset.model_name = model_name
                asset.serial_number = serial_number
                asset.vendor = vendor
                asset.version = version
                asset.license_key = license_key
                asset.host_server = host_server
                asset.department = department
                asset.assigned_user = assigned_user
                asset.status = status
                asset.ip_address = ip_address
                asset.mac_address = mac_address
                asset.purchase_date = purchase_date
                asset.warranty_expiry = warranty_expiry
                asset.compliance_status = compliance_status
                asset.risk_level = risk_level
                asset.remediation_plan = remediation_plan
                asset.seats_purchased = seats_purchased
                asset.seats_allocated = seats_allocated
                asset.remarks = remarks
                for key, value in metadata.items():
                    setattr(asset, key, value)
                asset.save()

                log_activity(
                    request=request,
                    action='UPDATE_ASSET',
                    module='Assets',
                    description=f"Updated asset details for [{asset.asset_tag}] at {loc.name}."
                )
                messages.success(request, f"Asset '{asset.asset_tag}' updated successfully!")

        except ValidationError as error:
            return render(request, 'devices/asset_form.html', {
                **form_context(), 'asset_tag_error': error.messages[0],
            }, status=400)

        return redirect('asset_list')

    # Pre-select location if passed via GET query ?location=id
    selected_loc_id = request.GET.get('location')
    if selected_loc_id:
        try:
            selected_loc_id = int(selected_loc_id)
        except ValueError:
            selected_loc_id = None

    context = {**form_context(), 'selected_loc_id': selected_loc_id}
    return render(request, 'devices/asset_form.html', context)


@roles_required(*DASHBOARD_ROUTES)
def software_list_view(request):
    """
    Software & License Management (SLM) Hub:
    Tracks commercial licenses, open-source software, and identifies
    unlicensed / cracked pirated software with security risk levels & remediation plans.
    """
    visible_locs = visible_locations(request.user)
    software_qs = Asset.objects.filter(
        location__in=visible_locs
    ).filter(
        Q(asset_nature='LOGICAL') |
        Q(device_type__category__name__icontains='software') |
        Q(device_type__category__name__icontains='license')
    ).select_related(
        'device_type', 'device_type__category', 'location', 'owning_company'
    )

    # Filters
    loc_filter = request.GET.get('location', '').strip()
    compliance_filter = request.GET.get('compliance', '').strip()
    risk_filter = request.GET.get('risk', '').strip()
    remediation_filter = request.GET.get('remediation', '').strip()
    search_query = request.GET.get('q', '').strip()

    if loc_filter:
        software_qs = software_qs.filter(location_id=loc_filter)

    if compliance_filter:
        software_qs = software_qs.filter(compliance_status=compliance_filter)

    if risk_filter:
        software_qs = software_qs.filter(risk_level=risk_filter)

    if remediation_filter:
        software_qs = software_qs.filter(remediation_plan=remediation_filter)

    if search_query:
        software_qs = software_qs.filter(
            Q(asset_tag__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(license_key__icontains=search_query) |
            Q(model_name__icontains=search_query) |
            Q(version__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(vendor__icontains=search_query) |
            Q(assigned_user__icontains=search_query) |
            Q(department__icontains=search_query) |
            Q(host_server__icontains=search_query)
        )

    # KPI Metrics across all visible software
    all_software_qs = Asset.objects.filter(
        location__in=visible_locs
    ).filter(
        Q(asset_nature='LOGICAL') |
        Q(device_type__category__name__icontains='software') |
        Q(device_type__category__name__icontains='license')
    )
    total_software = all_software_qs.count()
    cracked_count = all_software_qs.filter(compliance_status='CRACKED_PIRATED').count()
    high_critical_risk = all_software_qs.filter(risk_level__in=['HIGH', 'CRITICAL']).count()
    genuine_count = all_software_qs.filter(compliance_status='GENUINE').count()
    open_source_count = all_software_qs.filter(compliance_status='FREE_OPEN_SOURCE').count()

    today = timezone.now().date()
    in_30_days = today + timezone.timedelta(days=30)
    expiring_soon_count = all_software_qs.filter(
        warranty_expiry__gte=today,
        warranty_expiry__lte=in_30_days
    ).count()
    expired_count = all_software_qs.filter(
        warranty_expiry__lt=today
    ).count()

    piracy_percentage = round((cracked_count / total_software * 100), 1) if total_software > 0 else 0

    # Locations for filter
    locations = visible_locs.order_by('location_id', 'name')

    # Pagination
    paginator = Paginator(software_qs.order_by('-risk_level', '-id'), 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_software': total_software,
        'cracked_count': cracked_count,
        'high_critical_risk': high_critical_risk,
        'genuine_count': genuine_count,
        'open_source_count': open_source_count,
        'expiring_soon_count': expiring_soon_count,
        'expired_count': expired_count,
        'piracy_percentage': piracy_percentage,
        'locations': locations,
        'loc_filter': loc_filter,
        'compliance_filter': compliance_filter,
        'risk_filter': risk_filter,
        'remediation_filter': remediation_filter,
        'search_query': search_query,
        'compliance_choices': Asset.COMPLIANCE_CHOICES,
        'risk_level_choices': Asset.RISK_LEVEL_CHOICES,
        'remediation_choices': Asset.REMEDIATION_CHOICES,
    }
    return render(request, 'devices/software_list.html', context)


@roles_required(*CENTRAL_ROLES)
def category_list_view(request):
    """
    Manage Device Categories and Device Types with live count analytics,
    search filtering, and full edit/rename/delete lifecycle.
    """
    status = request.GET.get('status')
    tracking = request.GET.get('tracking')
    status = status if status in ('active', 'archived') else ''
    tracking = tracking if tracking in ('tagged', 'bulk') else ''

    filters = {name: value for name, value in {'status': status, 'tracking': tracking}.items() if value}
    catalog_url = reverse('category_list', query=filters)
    category_codes = dict(TAG_CATEGORY_CHOICES)

    # Handle POST actions (Add, Edit, Delete)
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        tag_category_code = request.POST.get('tag_category_code', '').strip().upper()
        if action_type in ('add_device', 'edit_device') and tag_category_code and tag_category_code not in category_codes:
            messages.error(request, 'Select a valid tag category code.')
            return redirect(catalog_url)

        if action_type == 'add_device':
            cat_id = request.POST.get('category_id')
            dev_name = request.POST.get('name', '').strip()
            is_count_only = request.POST.get('is_count_only') == '1'
            remarks = request.POST.get('remarks', '').strip()

            if cat_id and dev_name:
                cat = get_object_or_404(DeviceCategory, id=cat_id)
                dev, created = DeviceType.objects.get_or_create(
                    category=cat,
                    name=dev_name,
                    defaults={
                        'tag_category_code': tag_category_code,
                        'order': cat.devices.count() + 1,
                        'is_count_only': is_count_only,
                        'remarks': remarks
                    }
                )
                if created:
                    log_activity(
                        request=request,
                        action='CREATE_DEVICE_TYPE',
                        module='Categories',
                        description=f"Added new device item: '{dev_name}' under category '{cat.name}'."
                    )
                    messages.success(request, f"Device type '{dev_name}' created successfully under {cat.name}!")
                else:
                    messages.info(request, f"Device type '{dev_name}' already exists in {cat.name}.")

        elif action_type == 'edit_device':
            dev_id = request.POST.get('device_id')
            new_name = request.POST.get('name', '').strip()
            cat_id = request.POST.get('category_id')
            is_count_only = request.POST.get('is_count_only') == '1'
            remarks = request.POST.get('remarks', '').strip()

            if dev_id and new_name:
                dev = get_object_or_404(DeviceType, id=dev_id)
                old_name = dev.name
                if tag_category_code and tag_category_code != dev.tag_category_code:
                    if dev.assets.exists():
                        messages.error(request, 'Tag category code is locked because this device type has issued asset tags.')
                        return redirect(catalog_url)
                    dev.tag_category_code = tag_category_code
                dev.name = new_name
                if cat_id:
                    new_cat = get_object_or_404(DeviceCategory, id=cat_id)
                    dev.category = new_cat
                dev.is_count_only = is_count_only
                dev.remarks = remarks
                try:
                    dev.save()
                except ValidationError as error:
                    messages.error(request, ' '.join(error.messages))
                    return redirect(catalog_url)

                log_activity(
                    request=request,
                    action='UPDATE_DEVICE_TYPE',
                    module='Categories',
                    description=f"Updated device type from '{old_name}' to '{new_name}' (Category: {dev.category.name})."
                )
                messages.success(request, f"Device type '{new_name}' updated successfully!")

        elif action_type == 'delete_device':
            dev_id = request.POST.get('device_id')
            if dev_id:
                dev = get_object_or_404(DeviceType, id=dev_id)
                name = dev.name
                asset_count = dev.assets.count()

                if asset_count > 0:
                    messages.error(
                        request,
                        f"Cannot delete '{name}': {asset_count} physical asset(s) are currently registered under this device type. Please reassign or delete those assets first."
                    )
                else:
                    dev.delete()
                    log_activity(
                        request=request,
                        action='DELETE_DEVICE_TYPE',
                        module='Categories',
                        description=f"Deleted device type: '{name}'."
                    )
                    messages.success(request, f"Device type '{name}' has been deleted.")

        elif action_type == 'add_category':
            cat_name = request.POST.get('category_name', '').strip()
            cat_code = request.POST.get('category_code', '').strip().upper()
            if cat_name:
                if not cat_code:
                    cat_code = cat_name.upper().replace(' ', '_')
                DeviceCategory.objects.get_or_create(
                    code=cat_code,
                    defaults={'name': cat_name, 'order': DeviceCategory.objects.count() + 1}
                )
                log_activity(
                    request=request,
                    action='CREATE_CATEGORY',
                    module='Categories',
                    description=f"Added new category: '{cat_name}' ({cat_code})."
                )
                messages.success(request, f"Category '{cat_name}' created!")

        elif action_type == 'edit_category':
            cat_id = request.POST.get('category_id')
            cat_name = request.POST.get('category_name', '').strip()
            if cat_id and cat_name:
                cat = get_object_or_404(DeviceCategory, id=cat_id)
                old_name = cat.name
                cat.name = cat_name
                cat.save()
                log_activity(
                    request=request,
                    action='UPDATE_CATEGORY',
                    module='Categories',
                    description=f"Renamed category '{old_name}' to '{cat_name}'."
                )
                messages.success(request, f"Category renamed to '{cat_name}'!")

        return redirect(catalog_url)

    devices = DeviceType.objects.all()
    active = Q(is_active=True, category__is_active=True)
    if status == 'active':
        devices = devices.filter(active)
    elif status == 'archived':
        devices = devices.exclude(active)
    if tracking:
        devices = devices.filter(is_count_only=tracking == 'bulk')

    annotated_devices = devices.annotate(
        total_assets=Count('assets', distinct=True),
        in_use_assets=Count('assets', filter=Q(assets__status='IN_USE'), distinct=True),
        backup_assets=Count('assets', filter=Q(assets__status='BACKUP'), distinct=True),
        faulty_assets=Count('assets', filter=Q(assets__status__in=['FAULTY', 'SCRAP']), distinct=True),
    ).order_by('order', 'name')

    all_categories = DeviceCategory.objects.order_by('order', 'name')
    categories = all_categories.prefetch_related(
        Prefetch('devices', queryset=annotated_devices)
    ).annotate(
        category_assets_count=Count('devices__assets', filter=Q(devices__in=devices), distinct=True),
    )
    if status or tracking:
        categories = categories.filter(Exists(devices.filter(category_id=OuterRef('pk'))))

    # Overall KPIs
    total_categories = all_categories.count()
    total_device_types = DeviceType.objects.count()
    total_tracked_assets = Asset.objects.count()
    serial_tracked_count = DeviceType.objects.filter(is_count_only=False).count()
    bulk_count_only = DeviceType.objects.filter(is_count_only=True).count()

    context = {
        'categories': categories,
        'all_categories': all_categories,
        'catalog_status': status,
        'tag_category_choices': TAG_CATEGORY_CHOICES,
        'tracking_mode': tracking,
        'total_categories': total_categories,
        'total_device_types': total_device_types,
        'total_tracked_assets': total_tracked_assets,
        'serial_tracked_count': serial_tracked_count,
        'bulk_count_only': bulk_count_only,
    }
    return render(request, 'devices/category_list.html', context)


def scoped_asset(request, asset_id):
    assets = Asset.objects.select_related('device_type', 'location', 'location__company', 'owning_company')
    return get_object_or_404(assets, pk=asset_id, location__in=visible_locations(request.user))


def asset_label_url(request, asset):
    if asset.asset_nature != 'PHYSICAL':
        return None
    try:
        parts = urlsplit(request_preferences(request).get('application_url') or '')
    except ValueError:
        return None
    hostname = (parts.hostname or '').lower()
    if parts.scheme != 'https' or not hostname or parts.username or parts.password:
        return None
    if hostname in ('localhost', '127.0.0.1', '::1') or hostname.endswith('.localhost'):
        return None
    asset_path = reverse('asset_detail', args=[asset.pk])
    prefix = parts.path.rstrip('/')
    if prefix and not asset_path.startswith(prefix + '/'):
        asset_path = prefix + asset_path
    return urlunsplit(('https', parts.netloc, asset_path, '', ''))


@roles_required(*DASHBOARD_ROUTES)
@require_safe
def asset_detail_view(request, asset_id):
    asset = scoped_asset(request, asset_id)
    return render(request, 'devices/asset_detail.html', {
        'asset': asset, 'label_url': asset_label_url(request, asset),
        'status_label': dict(asset_status_choices(request_preferences(request))).get(asset.status, asset.get_status_display()),
    })


@roles_required(*DASHBOARD_ROUTES)
@require_safe
def asset_label_qr_view(request, asset_id):
    asset = scoped_asset(request, asset_id)
    label_url = asset_label_url(request, asset)
    if not label_url:
        raise Http404('A physical asset and a configured HTTPS application URL are required.')
    import qrcode
    from qrcode.image.svg import SvgPathImage

    image = qrcode.make(label_url, image_factory=SvgPathImage)
    response = HttpResponse(image.to_string(), content_type='image/svg+xml')
    response['Cache-Control'] = 'private, no-store'
    return response


@roles_required(*DASHBOARD_ROUTES)
@require_http_methods(['GET', 'HEAD', 'POST'])
def asset_retire_view(request, asset_id):
    assets = Asset.objects.filter(location__in=visible_locations(request.user))
    if request.method == 'POST':
        with transaction.atomic():
            asset = get_object_or_404(assets.select_for_update(), pk=asset_id)
            if not asset.retired_at:
                asset.status = 'SCRAP'
                asset.is_active = False
                asset.retired_at = timezone.now()
                asset.save(update_fields=['status', 'is_active', 'retired_at', 'updated_at'])
                log_activity(request, 'RETIRE_ASSET', 'Assets', f'Retired asset [{asset.asset_tag}].')
                messages.success(request, f'Asset “{asset.asset_tag}” retired. Its tag remains reserved.')
        return redirect('asset_detail', asset_id=asset_id)
    asset = get_object_or_404(assets, pk=asset_id)
    if asset.retired_at:
        return redirect('asset_detail', asset_id=asset.pk)
    return render(request, 'devices/asset_retire.html', {'asset': asset})


@roles_required(*CENTRAL_ROLES)
def download_sample_asset_csv_view(request):
    """
    Generates and downloads a pre-formatted sample or blank CSV template for importing assets.
    Supports location selection (?location=LOC_ID) and asset nature (?nature=PHYSICAL|LOGICAL|ALL) and blank mode (?blank=yes).
    """
    loc_param = request.GET.get('location', '').strip()
    nature = request.GET.get('nature', 'PHYSICAL').upper().strip()
    is_blank = request.GET.get('blank', 'no').lower().strip() in ('yes', '1', 'true')

    target_loc_code = 'LOC-001'
    target_loc_name = 'Akij House (Corporate HQ)'
    loc_file_suffix = 'generic'

    if loc_param:
        loc = None
        if loc_param.isdigit():
            loc = Location.objects.filter(id=int(loc_param)).first()
        if not loc:
            loc = Location.objects.filter(location_id__iexact=loc_param).first() or Location.objects.filter(code__iexact=loc_param).first()
        if loc:
            target_loc_code = loc.location_id
            target_loc_name = loc.name
            loc_file_suffix = loc.location_id.replace('-', '_').lower()

    if is_blank:
        filename = f"akij_asset_template_{loc_file_suffix}_{nature.lower()}_blank.csv"
    else:
        filename = f"akij_asset_template_{loc_file_suffix}_{nature.lower()}_sample.csv"

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    if nature == 'LOGICAL':
        writer.writerow([
            'asset_tag',
            'device_type',
            'location_code_or_id',
            'vendor',
            'version',
            'license_key',
            'host_server',
            'department',
            'assigned_user',
            'status',
            'purchase_date',
            'warranty_expiry',
            'remarks'
        ])
        if not is_blank:
            writer.writerow([
                'AST-LOG-0001',
                'Software License (OS / Office)',
                target_loc_code,
                'Microsoft Corporation',
                'Windows 11 Pro Enterprise',
                'W269N-WFGWX-YVC9B-4J6C9-T83GX',
                'Client Endpoints',
                'Accounts & Finance',
                'Md. Aminur Rahman',
                'IN_USE',
                '2024-01-01',
                '2027-12-31',
                'Akij Group Volume Licensing'
            ])
            writer.writerow([
                'AST-LOG-0002',
                'Enterprise ERP User License',
                target_loc_code,
                'Oracle Corporation',
                'ERP Production Core v12',
                'ORCL-ERP-AKIJ-9981',
                'Enterprise Cloud',
                'Supply Chain & Logistics',
                'Factory GM',
                'IN_USE',
                '2023-06-15',
                '2025-06-14',
                'Dedicated Named User License'
            ])
            writer.writerow([
                'AST-LOG-0003',
                'Cloud Virtual Server / VM',
                target_loc_code,
                'Amazon Web Services',
                'Ubuntu 22.04 LTS (t3.xlarge)',
                'i-0ab4c12d34ef56789',
                'AWS ap-south-1',
                'IT Infrastructure',
                'DevOps Team',
                'IN_USE',
                '2023-03-01',
                '',
                'Production Database Cluster Node'
            ])
            writer.writerow([
                'AST-LOG-0004',
                'SSL / TLS Certificate',
                target_loc_code,
                'DigiCert Inc.',
                'Wildcard SSL (*.akij.net)',
                'CERT-DC-2024-8871',
                'HAProxy Load Balancer',
                'IT Infrastructure',
                'Network Security',
                'IN_USE',
                '2024-02-10',
                '2025-02-09',
                'Corporate Portal Certificate'
            ])

    elif nature in ('ALL', 'COMPREHENSIVE'):
        writer.writerow([
            'asset_tag',
            'asset_nature',
            'device_type',
            'location_code_or_id',
            'brand',
            'model_name',
            'serial_number',
            'vendor',
            'version',
            'license_key',
            'host_server',
            'department',
            'assigned_user',
            'status',
            'ip_address',
            'mac_address',
            'purchase_date',
            'warranty_expiry',
            'remarks'
        ])
        if not is_blank:
            writer.writerow([
                'APL-LAP-10001',
                'PHYSICAL',
                'Laptop',
                target_loc_code,
                'Dell',
                'Latitude 5430',
                'SN-DL5430-9901',
                '',
                '',
                '',
                '',
                'Accounts & Finance',
                'Md. Aminur Rahman',
                'IN_USE',
                '192.168.10.45',
                '00:14:22:01:23:45',
                '2023-01-15',
                '2026-01-14',
                'Core i7, 16GB RAM, 512GB SSD'
            ])
            writer.writerow([
                'AST-LOG-0001',
                'LOGICAL',
                'Software License (OS / Office)',
                target_loc_code,
                '',
                '',
                '',
                'Microsoft Corporation',
                'Windows 11 Pro Enterprise',
                'W269N-WFGWX-YVC9B-4J6C9-T83GX',
                'Client Endpoints',
                'Accounts & Finance',
                'Md. Aminur Rahman',
                'IN_USE',
                '',
                '',
                '2024-01-01',
                '2027-12-31',
                'Akij Group Volume Licensing'
            ])
            writer.writerow([
                'APL-DSK-10002',
                'PHYSICAL',
                'Desktop',
                target_loc_code,
                'HP',
                'ProDesk 400 G6',
                'SN-HP400-8812',
                '',
                '',
                '',
                '',
                'Quality Control (QC)',
                'Engr. Rafiqul Islam',
                'IN_USE',
                '10.20.2.14',
                '00:1B:44:11:22:33',
                '2022-06-20',
                '2025-06-19',
                'Factory QC Lab station'
            ])
            writer.writerow([
                'APL-SWT-10003',
                'PHYSICAL',
                'Microtik Router',
                target_loc_code,
                'MikroTik',
                'CCR1009-7G-1C-1S+',
                'SN-MKCCR-99120',
                '',
                '',
                '',
                '',
                'IT Network Room',
                'Network Team',
                'IN_USE',
                '10.20.1.1',
                '00:0C:42:F1:8A:2B',
                '2022-01-10',
                '2025-01-09',
                'Core gateway router'
            ])
    else:  # PHYSICAL
        writer.writerow([
            'asset_tag',
            'device_type',
            'location_code_or_id',
            'brand',
            'model_name',
            'serial_number',
            'department',
            'assigned_user',
            'status',
            'ip_address',
            'mac_address',
            'purchase_date',
            'warranty_expiry',
            'remarks'
        ])
        if not is_blank:
            writer.writerow([
                'APL-LAP-10001',
                'Laptop',
                target_loc_code,
                'Dell',
                'Latitude 5430',
                'SN-DL5430-9901',
                'Accounts & Finance',
                'Md. Aminur Rahman',
                'IN_USE',
                '192.168.10.45',
                '00:14:22:01:23:45',
                '2023-01-15',
                '2026-01-14',
                'Core i7, 16GB RAM, 512GB SSD'
            ])
            writer.writerow([
                'APL-DSK-10002',
                'Desktop',
                target_loc_code,
                'HP',
                'ProDesk 400 G6',
                'SN-HP400-8812',
                'Quality Control (QC)',
                'Engr. Rafiqul Islam',
                'IN_USE',
                '10.20.2.14',
                '00:1B:44:11:22:33',
                '2022-06-20',
                '2025-06-19',
                'Factory QC Lab station'
            ])
            writer.writerow([
                '',
                'Microtik Router',
                target_loc_code,
                'MikroTik',
                'CCR1009-7G-1C-1S+',
                'SN-MKCCR-99120',
                'IT Network Room',
                'Network Team',
                'IN_USE',
                '10.20.1.1',
                '00:0C:42:F1:8A:2B',
                '2022-01-10',
                '2025-01-09',
                'Core gateway router'
            ])
            writer.writerow([
                '',
                'Managed Switch',
                target_loc_code,
                'Cisco',
                'Catalyst 2960X',
                'FOC2133S982',
                'Depot IT Server Rack',
                'IT Shared',
                'BACKUP',
                '',
                '',
                '2021-08-10',
                '2024-08-09',
                'Emergency buffer spare for depot'
            ])

    return response


@roles_required(*CENTRAL_ROLES)
def asset_import_csv_view(request):
    """
    Bulk import physical & logical IT assets location-wise via CSV upload.
    Supports location selection (force all rows vs fallback) and full logical asset ingestion.
    """
    locations = visible_locations(request.user).order_by('location_id', 'name')
    categories = DeviceCategory.objects.all()
    config = request_preferences(request)
    status_labels = {label.casefold(): code for code, label in asset_status_choices(config)}
    options = {
        key: {row.casefold(): row for row in config[setting].splitlines()}
        for key, (_, setting) in ASSET_METADATA.items()
    }

    import_results = None
    target_location_id = request.GET.get('location', '')
    location_mode = 'fallback'

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        target_location_id = request.POST.get('target_location') or request.POST.get('fallback_location') or ''
        location_mode = request.POST.get('location_mode', 'fallback')
        update_existing = request.POST.get('update_existing') == 'yes'

        if not csv_file:
            messages.error(request, "Please select a valid CSV file to upload.")
            return render(request, 'devices/asset_import_csv.html', {
                'locations': locations,
                'selected_location_id': target_location_id,
                'location_mode': location_mode,
            })

        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.txt')):
            messages.error(request, "Uploaded file must be a .csv format.")
            return render(request, 'devices/asset_import_csv.html', {
                'locations': locations,
                'selected_location_id': target_location_id,
                'location_mode': location_mode,
            })

        # Read file with encoding fallbacks (utf-8-sig for Excel BOM, utf-8, latin1)
        try:
            file_bytes = csv_file.read()
            try:
                decoded_file = file_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:
                    decoded_file = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    decoded_file = file_bytes.decode('latin-1')

            csv_reader = csv.reader(io.StringIO(decoded_file))
            rows = list(csv_reader)
        except Exception as e:
            messages.error(request, f"Failed to read CSV file: {str(e)}")
            return render(request, 'devices/asset_import_csv.html', {
                'locations': locations,
                'selected_location_id': target_location_id,
                'location_mode': location_mode,
            })

        if not rows:
            messages.error(request, "Uploaded CSV file is completely empty.")
            return render(request, 'devices/asset_import_csv.html', {
                'locations': locations,
                'selected_location_id': target_location_id,
                'location_mode': location_mode,
            })

        # Parse header row
        raw_headers = [h.strip().lower().replace(' ', '_').replace('-', '_') for h in rows[0]]
        header_map = {}
        for idx, h in enumerate(raw_headers):
            if h in ['asset_tag', 'tag', 'asset_id', 'barcode']:
                header_map['asset_tag'] = idx
            elif h in ['device_type', 'device', 'item_name', 'device_name', 'type', 'item']:
                header_map['device_type'] = idx
            elif h in ['location_code_or_id', 'location_code', 'location_id', 'location', 'site', 'branch', 'unit']:
                header_map['location'] = idx
            elif h in ('owning_company_code', 'owner_company_code'):
                header_map['owning_company_code'] = idx
            elif h in ['brand', 'manufacturer', 'make']:
                header_map['brand'] = idx
            elif h in ['model_name', 'model', 'model_no']:
                header_map['model_name'] = idx
            elif h in ['serial_number', 'serial_no', 'serial', 'sn']:
                header_map['serial_number'] = idx
            elif h in ['vendor', 'software_vendor', 'publisher']:
                header_map['vendor'] = idx
            elif h in ['version', 'edition', 'software_version']:
                header_map['version'] = idx
            elif h in ['license_key', 'license', 'product_key', 'subscription_id', 'key']:
                header_map['license_key'] = idx
            elif h in ['host_server', 'host', 'server', 'cloud_cluster']:
                header_map['host_server'] = idx
            elif h in ['asset_nature', 'nature', 'type_nature']:
                header_map['asset_nature'] = idx
            elif h in ['department', 'dept', 'section']:
                header_map['department'] = idx
            elif h in ['assigned_user', 'user', 'employee', 'custodian', 'assigned_to']:
                header_map['assigned_user'] = idx
            elif h == 'asset_condition' or (h == 'condition' and any(column in raw_headers for column in ('status', 'state'))):
                header_map['condition'] = idx
            elif h in ('criticality', 'ownership_type', 'procurement_type'):
                header_map[h] = idx
            elif h in ['status', 'condition', 'state']:
                header_map['status'] = idx
            elif h in ['ip_address', 'ip']:
                header_map['ip_address'] = idx
            elif h in ['mac_address', 'mac']:
                header_map['mac_address'] = idx
            elif h in ['purchase_date', 'purchase', 'activation_date']:
                header_map['purchase_date'] = idx
            elif h in ['warranty_expiry', 'warranty', 'license_expiry']:
                header_map['warranty_expiry'] = idx
            elif h in ['remarks', 'specification', 'specs', 'notes', 'comment']:
                header_map['remarks'] = idx

        if 'device_type' not in header_map:
            messages.error(request, "CSV Header must contain a 'device_type' (or 'device', 'item_name') column.")
            return render(request, 'devices/asset_import_csv.html', {
                'locations': locations,
                'selected_location_id': target_location_id,
                'location_mode': location_mode,
            })

        # Preload lookups for speed
        loc_by_id = {loc.location_id.upper(): loc for loc in Location.objects.all()}
        loc_by_code = {loc.code.upper(): loc for loc in Location.objects.filter(code__isnull=False)}
        loc_by_name = {loc.name.lower(): loc for loc in Location.objects.all()}

        owners_by_code = {owner.short_code.upper(): owner for owner in Company.objects.filter(is_active=True)}

        selected_loc_obj = None
        if target_location_id:
            try:
                selected_loc_obj = Location.objects.get(id=target_location_id)
            except Location.DoesNotExist:
                pass

        dt_by_name = {dt.name.lower(): dt for dt in DeviceType.objects.all()}
        default_user_cat = DeviceCategory.objects.filter(code='USERS').first() or DeviceCategory.objects.first()

        success_count = 0
        updated_count = 0
        skipped_count = 0
        error_rows = []
        seen_tags = set()

        data_rows = rows[1:]
        for row_idx, row in enumerate(data_rows, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue

            def get_val(key):
                if key in header_map and header_map[key] < len(row):
                    return row[header_map[key]].strip()
                return ''

            owner_code = get_val('owning_company_code').upper()
            owner = owners_by_code.get(owner_code)
            if owner_code and not owner:
                error_rows.append({'row': row_idx, 'reason': 'The owning company code is unknown or inactive.'})
                continue

            dev_type_val = get_val('device_type')
            if not dev_type_val:
                error_rows.append({'row': row_idx, 'reason': "Missing 'device_type'"})
                continue

            entries = {key: get_val(key) for key in ASSET_METADATA}
            invalid = [key for key, value in entries.items() if value and value.casefold() not in options[key]]
            if invalid:
                error_rows.append({'row': row_idx, 'reason': f'Invalid asset classification: {", ".join(invalid)}.'})
                continue
            metadata = {key: options[key][value.casefold()] for key, value in entries.items() if value}
            tag_val = normalize_asset_tag(get_val('asset_tag'))
            if tag_val:
                if tag_val in seen_tags:
                    error_rows.append({'row': row_idx, 'reason': 'This asset tag is repeated in the CSV file.'})
                    continue
                seen_tags.add(tag_val)

            # Resolve DeviceType
            dev_key = dev_type_val.lower()
            dt_obj = dt_by_name.get(dev_key)
            if not dt_obj:
                matching = [dt for name, dt in dt_by_name.items() if dev_key in name or name in dev_key]
                if matching:
                    dt_obj = matching[0]
                else:
                    dt_obj = DeviceType.objects.create(
                        category=default_user_cat,
                        name=dev_type_val,
                        order=DeviceType.objects.count() + 1
                    )
                    dt_by_name[dev_key] = dt_obj

            # Resolve Location
            target_loc = None
            if location_mode == 'force' and selected_loc_obj:
                target_loc = selected_loc_obj
            else:
                loc_val = get_val('location').upper()
                if loc_val:
                    target_loc = loc_by_id.get(loc_val) or loc_by_code.get(loc_val) or loc_by_name.get(loc_val.lower())
                if not target_loc:
                    target_loc = selected_loc_obj

            if not target_loc:
                error_rows.append({
                    'row': row_idx,
                    'reason': f"Location '{get_val('location')}' not recognized and no target/fallback location selected."
                })
                continue

            # Determine Asset Nature
            raw_nature = get_val('asset_nature').upper()
            if raw_nature in ('PHYSICAL', 'LOGICAL'):
                asset_nature = raw_nature
            elif dt_obj.category.code == 'LOGICAL':
                asset_nature = 'LOGICAL'
            else:
                asset_nature = 'PHYSICAL'

            # Normalize Status
            raw_status = get_val('status').upper().replace(' ', '_')
            status = 'IN_USE'
            if get_val('status').casefold() in status_labels:
                status = status_labels[get_val('status').casefold()]
            elif any(k in raw_status for k in ['BACKUP', 'SPARE']):
                status = 'BACKUP'
            elif any(k in raw_status for k in ['FAULTY', 'REPAIR', 'BROKEN', 'DEFECTIVE']):
                status = 'FAULTY'
            elif any(k in raw_status for k in ['SCRAP', 'DAMAGED', 'DISPOSED']):
                status = 'SCRAP'

            # Parse Dates
            purchase_date_val = get_val('purchase_date')
            purchase_date = None
            if purchase_date_val:
                try:
                    purchase_date = date.fromisoformat(purchase_date_val)
                except ValueError:
                    pass

            warranty_expiry_val = get_val('warranty_expiry')
            warranty_expiry = None
            if warranty_expiry_val:
                try:
                    warranty_expiry = date.fromisoformat(warranty_expiry_val)
                except ValueError:
                    pass

            brand_val = get_val('brand')
            model_val = get_val('model_name')
            sn_val = get_val('serial_number')
            vendor_val = get_val('vendor')
            version_val = get_val('version')
            license_val = get_val('license_key')
            host_val = get_val('host_server')
            dept_val = get_val('department')
            user_val = get_val('assigned_user')
            ip_val = get_val('ip_address') or None
            mac_val = get_val('mac_address') or None
            remarks_val = get_val('remarks')

            if asset_nature == 'LOGICAL':
                if not brand_val and vendor_val:
                    brand_val = vendor_val
                if not model_val and version_val:
                    model_val = version_val
                if not sn_val and license_val:
                    sn_val = license_val
                if not mac_val and host_val:
                    mac_val = host_val

            try:
                existing = Asset.objects.filter(asset_tag__iexact=tag_val).first() if tag_val else None
                if existing:
                    if update_existing:
                        asset = existing
                        if asset.retired_at:
                            raise ValidationError('This tag belongs to a retired asset and cannot be reissued or updated.')
                        asset.asset_nature = asset_nature
                        asset.device_type = dt_obj
                        asset.location = target_loc
                        if owner:
                            asset.owning_company = owner
                        if brand_val: asset.brand = brand_val
                        if model_val: asset.model_name = model_val
                        if sn_val: asset.serial_number = sn_val
                        if vendor_val: asset.vendor = vendor_val
                        if version_val: asset.version = version_val
                        if license_val: asset.license_key = license_val
                        if host_val: asset.host_server = host_val
                        if dept_val: asset.department = dept_val
                        if user_val: asset.assigned_user = user_val
                        asset.status = status
                        if ip_val: asset.ip_address = ip_val
                        if mac_val: asset.mac_address = mac_val
                        if purchase_date: asset.purchase_date = purchase_date
                        if warranty_expiry: asset.warranty_expiry = warranty_expiry
                        if remarks_val: asset.remarks = remarks_val
                        for key, value in metadata.items():
                            setattr(asset, key, value)
                        asset.save()
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    asset = Asset.objects.create(
                        asset_tag=tag_val or '',
                        asset_nature=asset_nature,
                        device_type=dt_obj,
                        location=target_loc,
                        owning_company=owner,
                        brand=brand_val,
                        model_name=model_val,
                        serial_number=sn_val,
                        vendor=vendor_val or None,
                        version=version_val or None,
                        license_key=license_val or None,
                        host_server=host_val or None,
                        department=dept_val,
                        assigned_user=user_val,
                        status=status,
                        ip_address=ip_val,
                        mac_address=mac_val,
                        purchase_date=purchase_date,
                        warranty_expiry=warranty_expiry,
                        remarks=remarks_val,
                        **metadata,
                    )
                    success_count += 1
            except ValidationError as error:
                error_rows.append({'row': row_idx, 'reason': ' '.join(error.messages)})
            except Exception:
                error_rows.append({'row': row_idx, 'reason': 'Unable to save this asset. Check the data and try again.'})

        # Record system activity log
        log_activity(
            request=request,
            action='IMPORT_CSV',
            module='Assets',
            description=f"CSV Bulk Import: {success_count} created, {updated_count} updated, {skipped_count} skipped, {len(error_rows)} errors."
        )

        import_results = {
            'success_count': success_count,
            'updated_count': updated_count,
            'skipped_count': skipped_count,
            'error_count': len(error_rows),
            'error_rows': error_rows,
        }

        if success_count > 0 or updated_count > 0:
            messages.success(
                request,
                f"CSV Import Completed: {success_count} new assets created, {updated_count} existing assets updated!"
            )
        elif len(error_rows) > 0:
            messages.warning(request, f"CSV processing completed with {len(error_rows)} error(s). Review details below.")

    context = {
        'locations': locations,
        'selected_location_id': target_location_id,
        'location_mode': location_mode,
        'import_results': import_results,
    }
    return render(request, 'devices/asset_import_csv.html', context)

