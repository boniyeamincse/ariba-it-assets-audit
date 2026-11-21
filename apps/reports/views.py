from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Sum
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, Role, role_for, roles_required, visible_locations
from apps.devices.models import DeviceCategory, DeviceType, Asset
from apps.audits.models import AuditSession, AuditItem
from apps.domains.models import DomainRecord
from apps.common.models import SystemActivityLog

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
