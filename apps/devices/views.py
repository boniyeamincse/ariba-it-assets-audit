from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.db.models import Q, Count, Exists, OuterRef, Prefetch
from django.urls import reverse
from datetime import date
import csv
import io

from apps.devices.models import DeviceCategory, DeviceType, Asset
from apps.locations.models import Location
from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, roles_required, visible_locations
from apps.common.utils import log_activity
from apps.common.preferences import request_preferences
from apps.devices.configuration import ASSET_METADATA, asset_status_choices

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
    search_query = request.GET.get('q', '').strip()

    if loc_filter:
        assets_qs = assets_qs.filter(location_id=loc_filter)

    if cat_filter:
        assets_qs = assets_qs.filter(device_type__category_id=cat_filter)

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
            Q(device_type__name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model_name__icontains=search_query) |
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
        'selected_device_type': selected_device_type,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': status_choices,
    }
    return render(request, 'devices/asset_list.html', context)


@roles_required(*DASHBOARD_ROUTES)
def asset_create_or_edit_view(request, asset_id=None):
    """
    Dynamic Location-Wise Asset Entry & Edit Form.
    """
    asset = None
    if asset_id:
        asset = get_object_or_404(Asset, id=asset_id, location__in=visible_locations(request.user))

    locations = visible_locations(request.user).order_by('location_id', 'name')
    categories = DeviceCategory.objects.prefetch_related('devices').all().order_by('order')
    device_types = DeviceType.objects.select_related('category').all().order_by('category__order', 'name')

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
        return {
            'asset': asset, 'locations': locations, 'categories': categories,
            'device_types': device_types, 'status_choices': status_choices,
            'metadata_fields': metadata_fields, 'currency': getattr(asset, 'currency', '') or config['asset_currency'],
            'default_warranty_months': config['default_warranty_months'],
        }

    if request.method == 'POST':
        asset_tag = request.POST.get('asset_tag', '').strip().upper()
        device_type_id = request.POST.get('device_type')
        location_id = request.POST.get('location')
        brand = request.POST.get('brand', '').strip()
        model_name = request.POST.get('model_name', '').strip()
        serial_number = request.POST.get('serial_number', '').strip()
        department = request.POST.get('department', '').strip()
        assigned_user = request.POST.get('assigned_user', '').strip()
        status = request.POST.get('status', 'IN_USE')
        ip_address = request.POST.get('ip_address', '').strip() or None
        mac_address = request.POST.get('mac_address', '').strip() or None
        purchase_date_str = request.POST.get('purchase_date', '').strip()
        warranty_expiry_str = request.POST.get('warranty_expiry', '').strip()
        remarks = request.POST.get('remarks', '').strip()

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

        purchase_date = date.fromisoformat(purchase_date_str) if purchase_date_str else None
        warranty_expiry = date.fromisoformat(warranty_expiry_str) if warranty_expiry_str else None

        is_new = asset is None

        if is_new:
            asset = Asset.objects.create(
                asset_tag=asset_tag or '',
                device_type=dev,
                location=loc,
                brand=brand,
                model_name=model_name,
                serial_number=serial_number,
                department=department,
                assigned_user=assigned_user,
                status=status,
                ip_address=ip_address,
                mac_address=mac_address,
                purchase_date=purchase_date,
                warranty_expiry=warranty_expiry,
                remarks=remarks,
                **metadata,
            )
            log_activity(
                request=request,
                action='CREATE_ASSET',
                module='Assets',
                description=f"Added asset [{asset.asset_tag}] {dev.name} to {loc.name} ({loc.location_id}). Assigned: {assigned_user or 'None'}."
            )
            messages.success(request, f"Asset '{asset.asset_tag}' ({dev.name}) successfully added to {loc.name}!")
        else:
            if asset_tag:
                asset.asset_tag = asset_tag
            asset.device_type = dev
            asset.location = loc
            asset.brand = brand
            asset.model_name = model_name
            asset.serial_number = serial_number
            asset.department = department
            asset.assigned_user = assigned_user
            asset.status = status
            asset.ip_address = ip_address
            asset.mac_address = mac_address
            asset.purchase_date = purchase_date
            asset.warranty_expiry = warranty_expiry
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

    # Handle POST actions (Add, Edit, Delete)
    if request.method == 'POST':
        action_type = request.POST.get('action_type')

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
                dev.name = new_name
                if cat_id:
                    new_cat = get_object_or_404(DeviceCategory, id=cat_id)
                    dev.category = new_cat
                dev.is_count_only = is_count_only
                dev.remarks = remarks
                dev.save()

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

        filters = {name: value for name, value in {'status': status, 'tracking': tracking}.items() if value}
        return redirect(reverse('category_list', query=filters))

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
        'tracking_mode': tracking,
        'total_categories': total_categories,
        'total_device_types': total_device_types,
        'total_tracked_assets': total_tracked_assets,
        'serial_tracked_count': serial_tracked_count,
        'bulk_count_only': bulk_count_only,
    }
    return render(request, 'devices/category_list.html', context)


@roles_required(*DASHBOARD_ROUTES)
def asset_delete_view(request, asset_id):
    """
    Deletes an asset record.
    """
    asset = get_object_or_404(Asset, id=asset_id, location__in=visible_locations(request.user))
    if request.method == 'POST':
        tag = asset.asset_tag
        loc_name = asset.location.name
        log_activity(
            request=request,
            action='DELETE_ASSET',
            module='Assets',
            description=f"Deleted asset [{tag}] from {loc_name}."
        )
        asset.delete()
        messages.success(request, f"Asset '{tag}' has been deleted.")
        return redirect('asset_list')

    return render(request, 'devices/asset_confirm_delete.html', {'asset': asset})


@roles_required(*CENTRAL_ROLES)
def download_sample_asset_csv_view(request):
    """
    Generates and downloads a pre-formatted sample CSV template for importing assets.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="akij_assets_import_template.csv"'

    writer = csv.writer(response)
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

    # Sample rows for guidance
    writer.writerow([
        'AST-8001',
        'Laptop',
        'LOC-001',
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
        'AST-8002',
        'Desktop',
        'LOC-002',
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
        'Managed Switch',
        'LOC-003',
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
    Bulk import physical IT assets location-wise via CSV upload.
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

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        fallback_loc_id = request.POST.get('fallback_location')
        update_existing = request.POST.get('update_existing') == 'yes'

        if not csv_file:
            messages.error(request, "Please select a valid CSV file to upload.")
            return render(request, 'devices/asset_import_csv.html', {'locations': locations})

        if not (csv_file.name.endswith('.csv') or csv_file.name.endswith('.txt')):
            messages.error(request, "Uploaded file must be a .csv format.")
            return render(request, 'devices/asset_import_csv.html', {'locations': locations})

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
            return render(request, 'devices/asset_import_csv.html', {'locations': locations})

        if not rows:
            messages.error(request, "Uploaded CSV file is completely empty.")
            return render(request, 'devices/asset_import_csv.html', {'locations': locations})

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
            elif h in ['brand', 'manufacturer', 'make']:
                header_map['brand'] = idx
            elif h in ['model_name', 'model', 'model_no']:
                header_map['model_name'] = idx
            elif h in ['serial_number', 'serial_no', 'serial', 'sn']:
                header_map['serial_number'] = idx
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
            elif h in ['purchase_date', 'purchase']:
                header_map['purchase_date'] = idx
            elif h in ['warranty_expiry', 'warranty']:
                header_map['warranty_expiry'] = idx
            elif h in ['remarks', 'specification', 'specs', 'notes', 'comment']:
                header_map['remarks'] = idx

        if 'device_type' not in header_map:
            messages.error(request, "CSV Header must contain a 'device_type' (or 'device', 'item_name') column.")
            return render(request, 'devices/asset_import_csv.html', {'locations': locations})

        # Preload lookups for speed
        loc_by_id = {loc.location_id.upper(): loc for loc in Location.objects.all()}
        loc_by_code = {loc.code.upper(): loc for loc in Location.objects.filter(code__isnull=False)}
        loc_by_name = {loc.name.lower(): loc for loc in Location.objects.all()}

        fallback_loc = None
        if fallback_loc_id:
            try:
                fallback_loc = Location.objects.get(id=fallback_loc_id)
            except Location.DoesNotExist:
                pass

        dt_by_name = {dt.name.lower(): dt for dt in DeviceType.objects.all()}
        default_user_cat = DeviceCategory.objects.filter(code='USERS').first() or DeviceCategory.objects.first()

        success_count = 0
        updated_count = 0
        skipped_count = 0
        error_rows = []

        data_rows = rows[1:]
        for row_idx, row in enumerate(data_rows, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue

            def get_val(key):
                if key in header_map and header_map[key] < len(row):
                    return row[header_map[key]].strip()
                return ''

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
            loc_val = get_val('location').upper()
            target_loc = None
            if loc_val:
                target_loc = loc_by_id.get(loc_val) or loc_by_code.get(loc_val) or loc_by_name.get(loc_val.lower())
            if not target_loc:
                target_loc = fallback_loc

            if not target_loc:
                error_rows.append({
                    'row': row_idx,
                    'reason': f"Location '{get_val('location')}' not recognized and no fallback location selected."
                })
                continue

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

            tag_val = get_val('asset_tag').upper()
            brand_val = get_val('brand')
            model_val = get_val('model_name')
            sn_val = get_val('serial_number')
            dept_val = get_val('department')
            user_val = get_val('assigned_user')
            ip_val = get_val('ip_address') or None
            mac_val = get_val('mac_address') or None
            remarks_val = get_val('remarks')

            try:
                if tag_val and Asset.objects.filter(asset_tag=tag_val).exists():
                    if update_existing:
                        asset = Asset.objects.get(asset_tag=tag_val)
                        asset.device_type = dt_obj
                        asset.location = target_loc
                        if brand_val: asset.brand = brand_val
                        if model_val: asset.model_name = model_val
                        if sn_val: asset.serial_number = sn_val
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
                        device_type=dt_obj,
                        location=target_loc,
                        brand=brand_val,
                        model_name=model_val,
                        serial_number=sn_val,
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
            except Exception as ex:
                error_rows.append({'row': row_idx, 'reason': f"Error saving asset: {str(ex)}"})

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
        'import_results': import_results,
    }
    return render(request, 'devices/asset_import_csv.html', context)

