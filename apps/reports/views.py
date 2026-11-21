from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Sum, Count
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, Role, role_for, roles_required, visible_locations
from apps.devices.models import DeviceCategory, DeviceType, Asset
from apps.audits.models import AuditSession, AuditItem
from apps.domains.models import DomainRecord
from apps.common.models import SystemActivityLog
from apps.locations.models import Location, Company
from apps.common.utils import log_activity

def dashboard_view(request):
    """
    Executive Analytics & KPI Dashboard for Sir and IT Management.
    """
    locations = visible_locations(request.user)
    audits = AuditSession.objects.filter(location__in=locations)
    items = AuditItem.objects.filter(audit_session__in=audits)
    total_locations = locations.count()
    audited_locations = audits.values('location').distinct().count()
    total_individual_assets = Asset.objects.filter(location__in=locations).count()
    total_devices = items.aggregate(t=Sum('total_qty'))['t'] or 0
    total_active = items.aggregate(t=Sum('active_qty'))['t'] or 0
    total_backup = items.aggregate(t=Sum('backup_qty'))['t'] or 0
    total_faulty = items.aggregate(t=Sum('faulty_qty'))['t'] or 0

    total_infra = items.filter(
        device_type__category__code='INFRASTRUCTURE'
    ).aggregate(t=Sum('total_qty'))['t'] or 0

    total_users = items.filter(
        device_type__category__code='USERS'
    ).aggregate(t=Sum('total_qty'))['t'] or 0

    # Top 8 devices
    top_devices = items.values('device_type__name').annotate(
        total=Sum('total_qty')
    ).order_by('-total')[:8]

    recent_audits = audits.select_related('location').order_by('-audit_date')[:10]

    # Resolve management scope & role title
    role = role_for(request.user)
    if request.user.is_superuser:
        role_label = "Super Administrator"
        scope_title = "Akij Group Enterprise IT Portfolio — All Locations"
    elif role == Role.HO_ADMIN and request.user.username == 'sir':
        role_label = "Executive Director / Central Management"
        scope_title = "Akij Group Corporate Governance — Master Enterprise Oversight"
    elif role == Role.HO_ADMIN:
        role_label = "Head Office Central Administrator"
        scope_title = "Head Office Executive Oversight — Multi-Location Network"
    elif role == Role.FACTORY_ADMIN:
        loc_names = ", ".join(locations.values_list('name', flat=True)) or "Assigned Factory"
        role_label = "Factory Operations Administrator"
        scope_title = f"Factory Operational Unit: {loc_names}"
    elif role == Role.DEPOT_ADMIN:
        loc_names = ", ".join(locations.values_list('name', flat=True)) or "Assigned Depot"
        role_label = "Regional Depot Administrator"
        scope_title = f"Regional Distribution Unit: {loc_names}"
    else:
        role_label = "Management Auditor"
        scope_title = "Akij Group IT Audit & Inventory Overview"

    if role in (Role.HO_ADMIN, Role.FACTORY_ADMIN, Role.DEPOT_ADMIN) and request.user.profile.custom_role_id:
        role_label = request.user.profile.role_label

    # Multi-location matrix summary for quick management decision-making
    location_summary = []
    for loc in locations:
        loc_assets_count = loc.assets.count()
        last_audit = loc.audit_sessions.order_by('-audit_date').first()
        audited_qty = last_audit.total_qty if last_audit else 0
        location_summary.append({
            'id': loc.id,
            'location_id': loc.location_id,
            'name': loc.name,
            'code': loc.code,
            'location_type': loc.get_location_type_display(),
            'city': loc.city or loc.division or 'Bangladesh',
            'tracked_assets': loc_assets_count,
            'audited_qty': audited_qty,
            'has_audit': last_audit is not None,
            'last_audit_id': last_audit.id if last_audit else None,
            'last_audit_date': last_audit.audit_date if last_audit else None,
            'audit_status': last_audit.get_status_display() if last_audit else 'Pending Audit',
        })

    today = timezone.now().date()
    assets_qs = Asset.objects.filter(location__in=locations)
    total_individual_assets = assets_qs.count()
    physical_assets_count = assets_qs.filter(asset_nature='PHYSICAL', retired_at__isnull=True).count()
    logical_assets_count = assets_qs.filter(asset_nature='LOGICAL', retired_at__isnull=True).count()
    assets_in_use = assets_qs.filter(status='IN_USE', retired_at__isnull=True).count()
    assets_backup = assets_qs.filter(status='BACKUP', retired_at__isnull=True).count()
    assets_faulty = assets_qs.filter(status__in=['FAULTY', 'SCRAP'], retired_at__isnull=True).count()
    assets_retired = assets_qs.filter(retired_at__isnull=False).count()

    # Software Compliance Metrics
    software_pirated_count = assets_qs.filter(compliance_status='CRACKED_PIRATED').count()
    software_unlicensed_count = assets_qs.filter(compliance_status__in=['UNLICENSED', 'UNLICENSED_EXPIRED', 'NON_COMPLIANT']).count()
    software_licensed_count = assets_qs.filter(compliance_status__in=['LICENSED', 'GENUINE', 'FREE_OPEN_SOURCE', 'OEM_BUNDLED']).count()

    # Domains & SSL Certificate Metrics
    all_domains = DomainRecord.objects.all()
    total_domains = all_domains.count()
    domains_active = all_domains.filter(status='ACTIVE', expiry_date__gte=today).count()
    domains_expiring_30 = all_domains.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count()
    domains_expired = all_domains.filter(expiry_date__lt=today).count()
    domains_ssl_issues = all_domains.filter(
        Q(ssl_status__in=['EXPIRING_SOON', 'EXPIRED']) |
        Q(ssl_expiry_date__lte=today + timedelta(days=30), ssl_expiry_date__isnull=False)
    ).count()
    domains_auto_renew_count = all_domains.filter(auto_renewal=True).count()
    domains_auto_renew_pct = round(domains_auto_renew_count / total_domains * 100, 1) if total_domains > 0 else 0

    # User & System Admin Metrics
    total_users_count = User.objects.filter(is_active=True).count()
    total_activity_logs = SystemActivityLog.objects.count()
    recent_logs_24h = SystemActivityLog.objects.filter(created_at__gte=timezone.now() - timedelta(hours=24)).count()

    # Location Coverage
    pending_audit_locations = max(0, total_locations - audited_locations)

    context = {
        'total_locations': total_locations,
        'audited_locations': audited_locations,
        'pending_audit_locations': pending_audit_locations,
        'total_individual_assets': total_individual_assets,
        'physical_assets_count': physical_assets_count,
        'logical_assets_count': logical_assets_count,
        'assets_in_use': assets_in_use,
        'assets_backup': assets_backup,
        'assets_faulty': assets_faulty,
        'assets_retired': assets_retired,
        'software_pirated_count': software_pirated_count,
        'software_unlicensed_count': software_unlicensed_count,
        'software_licensed_count': software_licensed_count,
        'total_domains': total_domains,
        'domains_active': domains_active,
        'domains_expiring_30': domains_expiring_30,
        'domains_expired': domains_expired,
        'domains_ssl_issues': domains_ssl_issues,
        'domains_auto_renew_pct': domains_auto_renew_pct,
        'total_users_count': total_users_count,
        'total_activity_logs': total_activity_logs,
        'recent_logs_24h': recent_logs_24h,
        'total_devices': total_devices,
        'total_active': total_active,
        'total_backup': total_backup,
        'total_faulty': total_faulty,
        'total_infra': total_infra,
        'total_users': total_users,
        'top_devices': top_devices,
        'recent_audits': recent_audits,
        'role_label': role_label,
        'scope_title': scope_title,
        'location_summary': location_summary,
        'is_central_management': role in CENTRAL_ROLES or request.user.is_superuser,
    }
    return render(request, 'dashboard.html', context)


@roles_required(*DASHBOARD_ROUTES)
def matrix_view(request):
    """
    Master Cross-Tab Matrix: Devices down the rows, Locations across the columns.
    """
    locations = visible_locations(request.user).order_by('location_type', 'name')
    categories = DeviceCategory.objects.prefetch_related('devices').all().order_by('order')

    # Build matrix data: {device_id: {loc_id: qty}}
    items = AuditItem.objects.filter(audit_session__location__in=locations).select_related('audit_session__location', 'device_type')
    matrix = {}
    loc_totals = {loc.id: 0 for loc in locations}
    grand_total = 0

    for itm in items:
        dev_id = itm.device_type_id
        loc_id = itm.audit_session.location_id
        if dev_id not in matrix:
            matrix[dev_id] = {}
        matrix[dev_id][loc_id] = matrix[dev_id].get(loc_id, 0) + itm.total_qty
        loc_totals[loc_id] += itm.total_qty
        grand_total += itm.total_qty

    # Structure by category
    category_data = []
    for cat in categories:
        dev_list = []
        for dev in cat.devices.all():
            counts = [matrix.get(dev.id, {}).get(loc.id, 0) for loc in locations]
            row_total = sum(counts)
            dev_list.append({
                'device': dev,
                'counts': counts,
                'total': row_total
            })
        category_data.append({
            'category': cat,
            'devices': dev_list
        })

    context = {
        'locations': locations,
        'category_data': category_data,
        'loc_totals': [loc_totals[loc.id] for loc in locations],
        'grand_total': grand_total,
    }
    return render(request, 'reports/matrix.html', context)


@roles_required(*DASHBOARD_ROUTES)
def export_excel_matrix(request):
    """
    Exports the complete multi-location matrix to an Excel workbook.
    """
    locations = list(visible_locations(request.user).order_by('location_type', 'name'))
    devices = DeviceType.objects.select_related('category').order_by('category__order', 'order', 'name')
    items = AuditItem.objects.filter(audit_session__location__in=locations).select_related('audit_session__location')

    matrix = {}
    for itm in items:
        matrix[(itm.device_type_id, itm.audit_session.location_id)] = itm.total_qty

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Master_IT_Asset_Matrix"

    # Styling
    hdr_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    tot_fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')
    grand_fill = PatternFill(start_color='C6E0B4', end_color='C6E0B4', fill_type='solid')
    hdr_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    bold_font = Font(name='Calibri', size=11, bold=True)
    border = Border(left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
                    top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'))

    # Headers
    headers = ['SL', 'Category', 'Device Type'] + [f"[{loc.location_id}] {loc.name}" for loc in locations] + ['Total Qty']
    ws.append(['Akij Group - Master IT Device Multi-Location Matrix'])
    ws.append([f'Generated on: {date.today().strftime("%Y-%m-%d")} | Official Audit Summary'])
    ws.append([])
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=4, column=col_idx)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center' if col_idx > 3 or col_idx == 1 else 'left')

    row_num = 5
    for idx, dev in enumerate(devices, 1):
        row = [idx, dev.category.name, dev.name]
        dev_total = 0
        for loc in locations:
            qty = matrix.get((dev.id, loc.id), 0)
            row.append(qty)
            dev_total += qty
        row.append(dev_total)
        ws.append(row)

        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=row_num, column=col_idx)
            c.border = border
            if col_idx == len(row):
                c.fill = tot_fill
                c.font = bold_font
            if col_idx > 3 or col_idx == 1:
                c.alignment = Alignment(horizontal='center')
        row_num += 1

    # Grand Total row
    tot_row = ['TOTAL', '', '']
    col_totals = [0] * (len(locations) + 1)
    for c_i, loc in enumerate(locations):
        c_tot = sum(matrix.get((d.id, loc.id), 0) for d in devices)
        tot_row.append(c_tot)
        col_totals[c_i] = c_tot
    grand_tot = sum(col_totals[:-1])
    tot_row.append(grand_tot)
    ws.append(tot_row)

    for col_idx in range(1, len(tot_row) + 1):
        c = ws.cell(row=row_num, column=col_idx)
        c.fill = grand_fill
        c.font = bold_font
        c.border = border
        if col_idx > 3 or col_idx == 1:
            c.alignment = Alignment(horizontal='center')

    # Auto column width
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_l = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 12)
    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 30

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="IT_Asset_Master_Matrix.xlsx"'
    wb.save(response)
    return response


# ==============================================================================
# REPORTS & ANALYTICS MODULE
# ==============================================================================

@roles_required(*DASHBOARD_ROUTES)
def report_hub_view(request):
    """
    Central Executive Reports & Analytics Hub.
    Provides gateway to 5 core executive reports, high-level portfolio health, and recent audit activity.
    """
    locations = visible_locations(request.user)
    today = timezone.now().date()

    # Hardware & Asset stats
    assets_qs = Asset.objects.filter(location__in=locations)
    total_assets = assets_qs.count()
    physical_assets = assets_qs.filter(asset_nature='PHYSICAL', retired_at__isnull=True).count()
    logical_assets = assets_qs.filter(asset_nature='LOGICAL', retired_at__isnull=True).count()
    in_use_assets = assets_qs.filter(status='IN_USE', retired_at__isnull=True).count()
    spare_assets = assets_qs.filter(status='BACKUP', retired_at__isnull=True).count()
    faulty_assets = assets_qs.filter(status__in=['FAULTY', 'SCRAP'], retired_at__isnull=True).count()
    retired_assets = assets_qs.filter(retired_at__isnull=False).count()

    # Software Compliance
    software_qs = assets_qs.filter(asset_nature='LOGICAL')
    total_software = software_qs.count()
    pirated_count = software_qs.filter(compliance_status='CRACKED_PIRATED').count()
    unlicensed_count = software_qs.filter(compliance_status__in=['UNLICENSED', 'UNLICENSED_EXPIRED', 'NON_COMPLIANT']).count()
    licensed_count = software_qs.filter(compliance_status__in=['LICENSED', 'GENUINE', 'FREE_OPEN_SOURCE', 'OEM_BUNDLED']).count()

    # Domain Governance (for central users)
    is_central = role_for(request.user) in CENTRAL_ROLES
    all_domains = DomainRecord.objects.all() if is_central else DomainRecord.objects.none()
    total_domains = all_domains.count()
    domains_expiring_30 = all_domains.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count()
    domains_expired = all_domains.filter(expiry_date__lt=today).count()
    domains_ssl_issues = all_domains.filter(
        Q(ssl_status__in=['EXPIRING_SOON', 'EXPIRED']) |
        Q(ssl_expiry_date__lte=today + timedelta(days=30), ssl_expiry_date__isnull=False)
    ).count()

    # Physical Audit Session metrics
    audit_sessions = AuditSession.objects.filter(location__in=locations)
    total_audits = audit_sessions.count()
    approved_audits = audit_sessions.filter(status='APPROVED').count()
    pending_audits = audit_sessions.exclude(status='APPROVED').count()
    total_locations = locations.count()

    # Recent export/audit activities
    recent_activity = SystemActivityLog.objects.filter(
        module__in=['Assets', 'Audits', 'Reports', 'Domains', 'Software']
    ).order_by('-created_at')[:8]

    context = {
        'total_assets': total_assets,
        'physical_assets': physical_assets,
        'logical_assets': logical_assets,
        'in_use_assets': in_use_assets,
        'spare_assets': spare_assets,
        'faulty_assets': faulty_assets,
        'retired_assets': retired_assets,
        'total_software': total_software,
        'pirated_count': pirated_count,
        'unlicensed_count': unlicensed_count,
        'licensed_count': licensed_count,
        'is_central': is_central,
        'total_domains': total_domains,
        'domains_expiring_30': domains_expiring_30,
        'domains_expired': domains_expired,
        'domains_ssl_issues': domains_ssl_issues,
        'total_audits': total_audits,
        'approved_audits': approved_audits,
        'pending_audits': pending_audits,
        'total_locations': total_locations,
        'recent_activity': recent_activity,
    }
    return render(request, 'reports/report_hub.html', context)


# ------------------------------------------------------------------------------
# 1. ASSET INVENTORY & LIFECYCLE REPORT
# ------------------------------------------------------------------------------

def _filter_report_assets(request):
    locations = visible_locations(request.user)
    qs = Asset.objects.filter(location__in=locations).select_related('location', 'device_type', 'device_type__category')

    loc_id = request.GET.get('location', '').strip()
    nature = request.GET.get('nature', '').strip()
    status = request.GET.get('status', '').strip()
    cat_id = request.GET.get('category', '').strip()
    warranty = request.GET.get('warranty', '').strip()
    search = request.GET.get('q', '').strip()

    if loc_id:
        qs = qs.filter(location_id=loc_id)
    if nature:
        qs = qs.filter(asset_nature=nature)
    if status:
        qs = qs.filter(status=status)
    if cat_id:
        qs = qs.filter(device_type__category_id=cat_id)

    today = timezone.now().date()
    if warranty == 'expired':
        qs = qs.filter(warranty_expiry__lt=today)
    elif warranty == 'expiring_30':
        qs = qs.filter(warranty_expiry__gte=today, warranty_expiry__lte=today + timedelta(days=30))
    elif warranty == 'valid':
        qs = qs.filter(warranty_expiry__gt=today + timedelta(days=30))

    if search:
        qs = qs.filter(
            Q(asset_tag__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(brand__icontains=search) |
            Q(model_name__icontains=search) |
            Q(assigned_user__icontains=search) |
            Q(ip_address__icontains=search)
        )

    filters = {
        'location_filter': loc_id,
        'nature_filter': nature,
        'status_filter': status,
        'category_filter': cat_id,
        'warranty_filter': warranty,
        'search_query': search,
    }
    return qs, filters, locations


@roles_required(*DASHBOARD_ROUTES)
def report_asset_inventory_view(request):
    """
    Detailed hardware asset inventory and lifecycle report.
    """
    assets_qs, filters, locations = _filter_report_assets(request)
    today = timezone.now().date()

    categories = DeviceCategory.objects.all().order_by('order', 'name')

    # Aggregates
    total_count = assets_qs.count()
    physical_count = assets_qs.filter(asset_nature='PHYSICAL').count()
    logical_count = assets_qs.filter(asset_nature='LOGICAL').count()
    in_use_count = assets_qs.filter(status='IN_USE').count()
    spare_count = assets_qs.filter(status='BACKUP').count()
    faulty_count = assets_qs.filter(status__in=['FAULTY', 'SCRAP']).count()
    retired_count = assets_qs.filter(status='RETIRED').count()

    # Category Breakdown
    cat_summary = assets_qs.values(
        'device_type__category__name', 'device_type__category__code'
    ).annotate(total=Count('id')).order_by('-total')

    # Location Breakdown
    loc_summary = assets_qs.values(
        'location__name', 'location__location_id', 'location__location_type'
    ).annotate(total=Count('id')).order_by('-total')

    context = {
        'assets': assets_qs.order_by('location__name', 'device_type__name', 'asset_tag'),
        'total_count': total_count,
        'physical_count': physical_count,
        'logical_count': logical_count,
        'in_use_count': in_use_count,
        'spare_count': spare_count,
        'faulty_count': faulty_count,
        'retired_count': retired_count,
        'cat_summary': cat_summary,
        'loc_summary': loc_summary,
        'locations': locations,
        'categories': categories,
        'today': today,
        **filters,
    }
    return render(request, 'reports/report_asset_inventory.html', context)


@roles_required(*DASHBOARD_ROUTES)
def export_report_asset_excel(request):
    """
    Exports asset inventory report to styled Excel spreadsheet.
    """
    assets_qs, _, _ = _filter_report_assets(request)
    assets_qs = assets_qs.order_by('location__name', 'device_type__name', 'asset_tag')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Asset_Inventory_Report"

    hdr_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    hdr_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.append(['Akij Group - Master Asset Inventory & Lifecycle Audit Report'])
    ws.cell(row=1, column=1).font = Font(name='Calibri', size=14, bold=True, color='1F4E78')
    ws.append([f'Generated on: {timezone.now().strftime("%Y-%m-%d %H:%M")} | Total Assets: {assets_qs.count()}'])
    ws.cell(row=2, column=1).font = Font(name='Calibri', size=10, italic=True, color='595959')
    ws.append([])

    headers = [
        'SL', 'Asset Tag', 'Location', 'Nature', 'Category', 'Device Type',
        'Brand', 'Model', 'Serial No', 'Status', 'Condition', 'Assigned User',
        'IP Address', 'Purchase Date', 'Warranty Expiry', 'Department'
    ]
    ws.append(headers)

    header_row = 4
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=header_row, column=col_idx)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for idx, asset in enumerate(assets_qs, start=1):
        row = [
            idx,
            asset.asset_tag,
            asset.location.name if asset.location else '',
            asset.get_asset_nature_display(),
            asset.device_type.category.name if asset.device_type and asset.device_type.category else '',
            asset.device_type.name if asset.device_type else '',
            asset.brand or '',
            asset.model_name or '',
            asset.serial_number or '',
            asset.get_status_display(),
            asset.condition or 'Good',
            asset.assigned_user or '',
            asset.ip_address or '',
            asset.purchase_date.strftime("%Y-%m-%d") if asset.purchase_date else '',
            asset.warranty_expiry.strftime("%Y-%m-%d") if asset.warranty_expiry else '',
            asset.department or ''
        ]
        ws.append(row)
        curr_row = header_row + idx
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=curr_row, column=col_idx)
            c.border = border
            c.font = Font(name='Calibri', size=10)
            if col_idx in (1, 4, 10, 11, 14, 15, 16):
                c.alignment = Alignment(horizontal='center')

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_l = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 11)

    log_activity(
        request=request,
        action='EXPORT_EXCEL',
        module='Reports',
        description=f"Exported {assets_qs.count()} asset records to Excel report."
    )

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Asset_Inventory_Report_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    wb.save(response)
    return response


# ------------------------------------------------------------------------------
# 2. SOFTWARE COMPLIANCE & CYBER RISK REPORT
# ------------------------------------------------------------------------------

def _filter_report_software(request):
    locations = visible_locations(request.user)
    qs = Asset.objects.filter(location__in=locations, asset_nature='LOGICAL').select_related('location', 'device_type')

    loc_id = request.GET.get('location', '').strip()
    compliance = request.GET.get('compliance', '').strip()
    search = request.GET.get('q', '').strip()

    if loc_id:
        qs = qs.filter(location_id=loc_id)
    if compliance:
        qs = qs.filter(compliance_status=compliance)
    if search:
        qs = qs.filter(
            Q(brand__icontains=search) |
            Q(model_name__icontains=search) |
            Q(asset_tag__icontains=search) |
            Q(assigned_user__icontains=search) |
            Q(license_key__icontains=search)
        )

    filters = {
        'location_filter': loc_id,
        'compliance_filter': compliance,
        'search_query': search,
    }
    return qs, filters, locations


@roles_required(*DASHBOARD_ROUTES)
def report_software_compliance_view(request):
    """
    Software license distribution, piracy risk detection and audit report.
    """
    software_qs, filters, locations = _filter_report_software(request)

    total_count = software_qs.count()
    pirated_count = software_qs.filter(compliance_status='CRACKED_PIRATED').count()
    unlicensed_count = software_qs.filter(compliance_status__in=['UNLICENSED', 'UNLICENSED_EXPIRED', 'NON_COMPLIANT']).count()
    licensed_count = software_qs.filter(compliance_status__in=['LICENSED', 'GENUINE', 'FREE_OPEN_SOURCE', 'OEM_BUNDLED']).count()
    compliance_rate = round(licensed_count / total_count * 100, 1) if total_count > 0 else 100

    # Risk hotspot by location
    loc_risk = software_qs.values(
        'location__name', 'location__location_id'
    ).annotate(
        total=Count('id'),
        pirated=Count('id', filter=Q(compliance_status='CRACKED_PIRATED')),
        unlicensed=Count('id', filter=Q(compliance_status__in=['UNLICENSED', 'UNLICENSED_EXPIRED', 'NON_COMPLIANT']))
    ).order_by('-pirated', '-unlicensed')

    context = {
        'software_list': software_qs.order_by('-compliance_status', 'location__name', 'brand'),
        'total_count': total_count,
        'pirated_count': pirated_count,
        'unlicensed_count': unlicensed_count,
        'licensed_count': licensed_count,
        'compliance_rate': compliance_rate,
        'loc_risk': loc_risk,
        'locations': locations,
        'compliance_choices': Asset.COMPLIANCE_CHOICES,
        **filters,
    }
    return render(request, 'reports/report_software_compliance.html', context)


@roles_required(*DASHBOARD_ROUTES)
def export_report_software_excel(request):
    """
    Exports software compliance report to Excel.
    """
    software_qs, _, _ = _filter_report_software(request)
    software_qs = software_qs.order_by('-compliance_status', 'location__name', 'brand')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Software_Compliance_Audit"

    hdr_fill = PatternFill(start_color='7030A0', end_color='7030A0', fill_type='solid')
    hdr_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.append(['Akij Group - Software Compliance & Cyber Risk Audit Report'])
    ws.cell(row=1, column=1).font = Font(name='Calibri', size=14, bold=True, color='7030A0')
    ws.append([f'Generated on: {timezone.now().strftime("%Y-%m-%d %H:%M")} | Total Records: {software_qs.count()}'])
    ws.cell(row=2, column=1).font = Font(name='Calibri', size=10, italic=True, color='595959')
    ws.append([])

    headers = [
        'SL', 'Asset Tag', 'Location', 'Software Title / Brand', 'Version / Edition',
        'Compliance Status', 'License Seats', 'License Expiry', 'Assigned User / Workstation',
        'Audit Notes / Verification'
    ]
    ws.append(headers)

    header_row = 4
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=header_row, column=col_idx)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for idx, soft in enumerate(software_qs, start=1):
        row = [
            idx,
            soft.asset_tag,
            soft.location.name if soft.location else '',
            soft.brand or 'Software Application',
            soft.model_name or '',
            soft.get_compliance_status_display(),
            soft.seats_purchased,
            soft.warranty_expiry.strftime("%Y-%m-%d") if soft.warranty_expiry else 'Perpetual',
            soft.assigned_user or '',
            soft.remarks or ''
        ]
        ws.append(row)
        curr_row = header_row + idx
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=curr_row, column=col_idx)
            c.border = border
            c.font = Font(name='Calibri', size=10)
            if col_idx in (1, 6, 7, 8):
                c.alignment = Alignment(horizontal='center')

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_l = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 11)

    log_activity(
        request=request,
        action='EXPORT_EXCEL',
        module='Reports',
        description=f"Exported {software_qs.count()} software compliance records to Excel."
    )

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Software_Compliance_Report_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    wb.save(response)
    return response


# ------------------------------------------------------------------------------
# 3. DOMAINS & SSL GOVERNANCE REPORT
# ------------------------------------------------------------------------------

def _filter_report_domains(request):
    qs = DomainRecord.objects.select_related('company').all()
    comp_id = request.GET.get('company', '').strip()
    category = request.GET.get('category', '').strip()
    registrar = request.GET.get('registrar', '').strip()
    ssl = request.GET.get('ssl', '').strip()
    expiry_range = request.GET.get('expiry_range', '').strip()
    search = request.GET.get('q', '').strip()

    if comp_id:
        qs = qs.filter(company_id=comp_id)
    if category:
        qs = qs.filter(category=category)
    if registrar:
        qs = qs.filter(registrar=registrar)

    today = timezone.now().date()
    if ssl == 'issues':
        qs = qs.filter(
            Q(ssl_status__in=['EXPIRING_SOON', 'EXPIRED']) |
            Q(ssl_expiry_date__lte=today + timedelta(days=30), ssl_expiry_date__isnull=False)
        )
    elif ssl:
        qs = qs.filter(ssl_status=ssl)

    if expiry_range == 'expired':
        qs = qs.filter(expiry_date__lt=today)
    elif expiry_range == 'expiring_30':
        qs = qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
    elif expiry_range == 'expiring_60':
        qs = qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=60))
    elif expiry_range == 'expiring_90':
        qs = qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=90))

    if search:
        qs = qs.filter(
            Q(domain_name__icontains=search) |
            Q(primary_a_record_ip__icontains=search) |
            Q(technical_contact__icontains=search)
        )

    filters = {
        'company_filter': comp_id,
        'category_filter': category,
        'registrar_filter': registrar,
        'ssl_filter': ssl,
        'expiry_range': expiry_range,
        'search_query': search,
    }
    return qs, filters


@roles_required(*CENTRAL_ROLES)
def report_domains_ssl_view(request):
    """
    Corporate domain registry and SSL security governance report.
    """
    domains_qs, filters = _filter_report_domains(request)
    today = timezone.now().date()

    total_count = domains_qs.count()
    expired_count = domains_qs.filter(expiry_date__lt=today).count()
    expiring_30 = domains_qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count()
    ssl_issues = domains_qs.filter(
        Q(ssl_status__in=['EXPIRING_SOON', 'EXPIRED']) |
        Q(ssl_expiry_date__lte=today + timedelta(days=30), ssl_expiry_date__isnull=False)
    ).count()

    total_cost_usd = sum(d.annual_cost for d in domains_qs if d.currency == 'USD')
    total_cost_bdt = sum(d.annual_cost for d in domains_qs if d.currency == 'BDT')

    companies = Company.objects.filter(is_active=True).order_by('name')

    context = {
        'domains': domains_qs.order_by('expiry_date', 'domain_name'),
        'total_count': total_count,
        'expired_count': expired_count,
        'expiring_30': expiring_30,
        'ssl_issues': ssl_issues,
        'total_cost_usd': total_cost_usd,
        'total_cost_bdt': total_cost_bdt,
        'companies': companies,
        'category_choices': DomainRecord.CATEGORY_CHOICES,
        'registrar_choices': DomainRecord.REGISTRAR_CHOICES,
        'ssl_choices': DomainRecord.SSL_STATUS_CHOICES,
        **filters,
    }
    return render(request, 'reports/report_domains_ssl.html', context)


@roles_required(*CENTRAL_ROLES)
def export_report_domains_excel(request):
    """
    Exports domain & SSL governance report to Excel.
    """
    domains_qs, _ = _filter_report_domains(request)
    domains_qs = domains_qs.order_by('expiry_date', 'domain_name')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Domain_SSL_Governance"

    hdr_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    hdr_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.append(['Akij Group - Corporate Domain, DNS & SSL Governance Register'])
    ws.cell(row=1, column=1).font = Font(name='Calibri', size=14, bold=True, color='1F4E78')
    ws.append([f'Generated on: {timezone.now().strftime("%Y-%m-%d %H:%M")} | Total Records: {domains_qs.count()}'])
    ws.cell(row=2, column=1).font = Font(name='Calibri', size=10, italic=True, color='595959')
    ws.append([])

    headers = [
        'SL', 'Domain Name', 'Company', 'Classification', 'Registrar',
        'Annual Cost', 'Currency', 'Expiry Date', 'Days Left', 'Auto-Renew',
        'DNS Provider', 'Server IP', 'Mail Provider', 'SSL Status', 'SSL Expiry', 'IT Admin'
    ]
    ws.append(headers)

    header_row = 4
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=header_row, column=col_idx)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for idx, dom in enumerate(domains_qs, start=1):
        row = [
            idx,
            dom.domain_name,
            dom.company.name if dom.company else '',
            dom.get_category_display(),
            dom.get_registrar_display(),
            float(dom.annual_cost),
            dom.currency,
            dom.expiry_date.strftime("%Y-%m-%d") if dom.expiry_date else '',
            dom.days_until_expiry,
            'Yes' if dom.auto_renewal else 'No',
            dom.get_dns_provider_display(),
            dom.primary_a_record_ip or '',
            dom.get_mail_provider_display(),
            dom.get_ssl_status_display(),
            dom.ssl_expiry_date.strftime("%Y-%m-%d") if dom.ssl_expiry_date else '',
            dom.technical_contact or ''
        ]
        ws.append(row)
        curr_row = header_row + idx
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=curr_row, column=col_idx)
            c.border = border
            c.font = Font(name='Calibri', size=10)
            if col_idx in (1, 6, 7, 8, 9, 10, 14, 15):
                c.alignment = Alignment(horizontal='center')

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_l = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 11)

    log_activity(
        request=request,
        action='EXPORT_EXCEL',
        module='Reports',
        description=f"Exported {domains_qs.count()} domain records to Excel report."
    )

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Domain_SSL_Report_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    wb.save(response)
    return response


# ------------------------------------------------------------------------------
# 4. PHYSICAL AUDIT RECONCILIATION REPORT
# ------------------------------------------------------------------------------

def _get_audit_reconciliation_data(user, loc_filter=None, status_filter=None):
    locations = visible_locations(user).order_by('location_type', 'name')
    if loc_filter:
        locations = locations.filter(id=loc_filter)

    reconciliation_list = []
    total_physical_count = 0
    total_system_assets = 0
    total_variance = 0

    for loc in locations:
        last_session = AuditSession.objects.filter(location=loc).order_by('-audit_date').first()
        if status_filter and last_session and last_session.status != status_filter:
            continue
        if status_filter and not last_session and status_filter != 'NOT_AUDITED':
            continue

        counted_qty = AuditItem.objects.filter(audit_session__location=loc).aggregate(t=Sum('total_qty'))['t'] or 0
        sys_qty = Asset.objects.filter(location=loc, asset_nature='PHYSICAL', retired_at__isnull=True).count()
        variance = counted_qty - sys_qty

        total_physical_count += counted_qty
        total_system_assets += sys_qty
        total_variance += variance

        reconciliation_list.append({
            'location': loc,
            'session': last_session,
            'counted_qty': counted_qty,
            'sys_qty': sys_qty,
            'variance': variance,
            'status': last_session.get_status_display() if last_session else 'Not Audited',
            'status_code': last_session.status if last_session else 'NOT_AUDITED',
        })

    return reconciliation_list, total_physical_count, total_system_assets, total_variance, locations


@roles_required(*DASHBOARD_ROUTES)
def report_audit_reconciliation_view(request):
    """
    Reconciliation report comparing physical count with system assets per location.
    """
    loc_filter = request.GET.get('location', '').strip()
    status_filter = request.GET.get('status', '').strip()

    recon_data, total_counted, total_system, total_var, locations = _get_audit_reconciliation_data(
        request.user, loc_filter=loc_filter, status_filter=status_filter
    )

    context = {
        'reconciliation_list': recon_data,
        'total_locations': len(recon_data),
        'total_counted': total_counted,
        'total_system': total_system,
        'total_variance': total_var,
        'locations': locations,
        'location_filter': loc_filter,
        'status_filter': status_filter,
        'status_choices': AuditSession.STATUS_CHOICES,
    }
    return render(request, 'reports/report_audit_reconciliation.html', context)


@roles_required(*DASHBOARD_ROUTES)
def export_report_audit_excel(request):
    """
    Exports physical audit reconciliation to Excel.
    """
    loc_filter = request.GET.get('location', '').strip()
    status_filter = request.GET.get('status', '').strip()

    recon_data, total_counted, total_system, total_var, _ = _get_audit_reconciliation_data(
        request.user, loc_filter=loc_filter, status_filter=status_filter
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Audit_Reconciliation"

    hdr_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    hdr_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.append(['Akij Group - Physical Stock Count vs Inventory Reconciliation Report'])
    ws.cell(row=1, column=1).font = Font(name='Calibri', size=14, bold=True, color='1F4E78')
    ws.append([f'Generated on: {timezone.now().strftime("%Y-%m-%d %H:%M")} | Total Locations: {len(recon_data)}'])
    ws.cell(row=2, column=1).font = Font(name='Calibri', size=10, italic=True, color='595959')
    ws.append([])

    headers = [
        'SL', 'Location Code', 'Location Name', 'Location Type', 'Audit Date',
        'Lead Auditor', 'Audit Status', 'Physical Count', 'System Assets', 'Variance (+/-)'
    ]
    ws.append(headers)

    header_row = 4
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=header_row, column=col_idx)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = border

    for idx, item in enumerate(recon_data, start=1):
        loc = item['location']
        sess = item['session']
        row = [
            idx,
            loc.location_id,
            loc.name,
            loc.get_location_type_display(),
            sess.audit_date.strftime("%Y-%m-%d") if sess and sess.audit_date else 'N/A',
            sess.auditor_name if sess else 'N/A',
            item['status'],
            item['counted_qty'],
            item['sys_qty'],
            item['variance']
        ]
        ws.append(row)
        curr_row = header_row + idx
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(row=curr_row, column=col_idx)
            c.border = border
            c.font = Font(name='Calibri', size=10)
            if col_idx in (1, 2, 4, 5, 7, 8, 9, 10):
                c.alignment = Alignment(horizontal='center')

    # Total row
    tot_row = ['TOTAL', '', f'{len(recon_data)} Locations', '', '', '', '', total_counted, total_system, total_var]
    ws.append(tot_row)
    tot_row_idx = header_row + len(recon_data) + 1
    for col_idx in range(1, len(tot_row) + 1):
        c = ws.cell(row=tot_row_idx, column=col_idx)
        c.border = border
        c.fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')
        c.font = Font(name='Calibri', size=11, bold=True)
        if col_idx in (1, 8, 9, 10):
            c.alignment = Alignment(horizontal='center')

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_l = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col_letter].width = max(max_l + 3, 11)

    log_activity(
        request=request,
        action='EXPORT_EXCEL',
        module='Reports',
        description=f"Exported audit reconciliation data for {len(recon_data)} locations to Excel report."
    )

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Audit_Reconciliation_Report_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    wb.save(response)
    return response
