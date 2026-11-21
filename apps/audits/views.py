from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from datetime import date

from apps.devices.models import DeviceCategory, DeviceType
from apps.audits.models import AuditSession, AuditItem
from apps.common.utils import log_activity
from apps.accounts.access import DASHBOARD_ROUTES, LOCAL_TYPES, role_for, roles_required, visible_locations

from django.core.paginator import Paginator

@roles_required(*DASHBOARD_ROUTES)
def audit_list_view(request):
    """
    List of all audit sessions across Head Office, Factories, and Depots
    with filtering, interactive KPIs, and pagination.
    """
    locations = visible_locations(request.user).order_by('location_type', 'name')
    audits_qs = AuditSession.objects.filter(location__in=locations).select_related('location', 'location__company')

    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    loc_filter = request.GET.get('location', '').strip()
    type_filter = request.GET.get('type', '').strip()

    # Pre-filter metrics for KPI cards
    total_audits = audits_qs.count()
    approved_count = audits_qs.filter(status='APPROVED').count()
    pending_count = audits_qs.exclude(status='APPROVED').count()
    audited_locations = audits_qs.values('location_id').distinct().count()

    if search:
        audits_qs = audits_qs.filter(
            Q(location__name__icontains=search) |
            Q(location__location_id__icontains=search) |
            Q(location__code__icontains=search) |
            Q(auditor_name__icontains=search) |
            Q(verified_by_name__icontains=search) |
            Q(remarks__icontains=search)
        )
    if status_filter:
        audits_qs = audits_qs.filter(status=status_filter)
    if loc_filter:
        audits_qs = audits_qs.filter(location_id=loc_filter)
    if type_filter:
        audits_qs = audits_qs.filter(location__location_type=type_filter)

    audits_qs = audits_qs.order_by('-audit_date', '-created_at')

    paginator = Paginator(audits_qs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'audits': page_obj,
        'locations': locations,
        'total_audits': total_audits,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'audited_locations': audited_locations,
        'status_choices': AuditSession.STATUS_CHOICES,
        'search_query': search,
        'status_filter': status_filter,
        'loc_filter': loc_filter,
        'type_filter': type_filter,
    }
    return render(request, 'audits/audit_list.html', context)


@roles_required(*DASHBOARD_ROUTES)
def audit_detail_view(request, audit_id):
    """
    Detailed view of a single audit session.
    """
    audit = get_object_or_404(AuditSession.objects.select_related('location', 'location__company'),
                              id=audit_id, location__in=visible_locations(request.user))
    infra_items = audit.items.filter(device_type__category__code='INFRASTRUCTURE').select_related('device_type')
    user_items = audit.items.filter(device_type__category__code='USERS').select_related('device_type')

    context = {
        'audit': audit,
        'infra_items': infra_items,
        'user_items': user_items,
    }
    return render(request, 'audits/audit_detail.html', context)


@roles_required(*DASHBOARD_ROUTES)
def audit_print_view(request, audit_id):
    """
    Formal print/PDF view with Akij letterhead and approval signatures for Sir.
    """
    audit = get_object_or_404(AuditSession.objects.select_related('location', 'location__company'),
                              id=audit_id, location__in=visible_locations(request.user))
    infra_items = audit.items.filter(device_type__category__code='INFRASTRUCTURE').select_related('device_type')
    user_items = audit.items.filter(device_type__category__code='USERS').select_related('device_type')

    context = {
        'audit': audit,
        'infra_items': infra_items,
        'user_items': user_items,
    }
    return render(request, 'audits/audit_print.html', context)


@roles_required(*DASHBOARD_ROUTES)
def audit_create_or_edit_view(request, audit_id=None):
    """
    Fast dynamic grid data-entry form for audits.
    """
    locations = visible_locations(request.user).order_by('name')
    scoped_audits = AuditSession.objects.filter(location__in=locations)
    role = role_for(request.user)
    local_admin = role in LOCAL_TYPES
    audit = None
    if audit_id:
        audit = get_object_or_404(scoped_audits, id=audit_id)
        if local_admin and audit.status != 'DRAFT':
            raise PermissionDenied

    eligible = Q(is_active=True)
    if audit:
        eligible |= Q(pk=audit.location_id)
    eligible_locations = locations.filter(eligible)
    selected_location_id = audit.location_id if audit else None
    if not audit and request.method != 'POST' and request.GET.get('location'):
        location_id = request.GET['location']
        if not location_id.isdecimal():
            raise Http404('Location not found.')
        selected_location_id = get_object_or_404(eligible_locations, pk=location_id).pk

    categories = DeviceCategory.objects.prefetch_related('devices').all().order_by('order')

    if request.method == 'POST':
        loc_id = request.POST.get('location')
        audit_date_str = request.POST.get('audit_date')
        auditor_name = request.POST.get('auditor_name', 'IT Audit Team')
        verified_by = request.POST.get('verified_by_name', '')
        remarks = request.POST.get('remarks', '')
        status = request.POST.get('status', 'DRAFT')

        if local_admin and status not in ('DRAFT', 'SUBMITTED'):
            raise PermissionDenied
        if local_admin:
            auditor_name = request.user.get_full_name() or request.user.username
            verified_by = ''
        if not loc_id or not loc_id.isdecimal():
            raise Http404('Location not found.')
        loc = get_object_or_404(eligible_locations, id=loc_id)
        audit_date = date.fromisoformat(audit_date_str) if audit_date_str else date.today()

        with transaction.atomic():
            if not audit:
                audit, created = scoped_audits.select_for_update().get_or_create(
                    location=loc,
                    audit_date=audit_date,
                    defaults={
                        'auditor_name': auditor_name,
                        'verified_by_name': verified_by,
                        'remarks': remarks,
                        'status': status
                    }
                )
                if local_admin and not created:
                    return redirect('audit_detail', audit_id=audit.id)
            else:
                audit = get_object_or_404(scoped_audits.select_for_update(), pk=audit_id)
                if local_admin and audit.status != 'DRAFT':
                    raise PermissionDenied
                audit.location = loc
                audit.audit_date = audit_date
                audit.auditor_name = auditor_name
                audit.verified_by_name = verified_by
                audit.remarks = remarks
                audit.status = status
                audit.save()

            # Process device items from POST form
            all_devices = DeviceType.objects.all()
            for dev in all_devices:
                active_key = f"active_{dev.id}"
                backup_key = f"backup_{dev.id}"
                faulty_key = f"faulty_{dev.id}"
                remarks_key = f"remarks_{dev.id}"

                active_qty = int(request.POST.get(active_key, 0) or 0)
                backup_qty = int(request.POST.get(backup_key, 0) or 0)
                faulty_qty = int(request.POST.get(faulty_key, 0) or 0)
                item_remarks = request.POST.get(remarks_key, '').strip()

                if active_qty > 0 or backup_qty > 0 or faulty_qty > 0 or item_remarks:
                    AuditItem.objects.update_or_create(
                        audit_session=audit,
                        device_type=dev,
                        defaults={
                            'active_qty': active_qty,
                            'backup_qty': backup_qty,
                            'faulty_qty': faulty_qty,
                            'remarks': item_remarks
                        }
                    )
                else:
                    # If 0 and previously existed, remove or set to 0
                    AuditItem.objects.filter(audit_session=audit, device_type=dev).delete()

        is_new_audit = audit_id is None
        log_activity(
            request=request,
            action='CREATE_AUDIT' if is_new_audit else 'UPDATE_AUDIT',
            module='Audits',
            description=f"{'Created new' if is_new_audit else 'Updated'} physical IT audit for {loc.name} on {audit.audit_date}. Total verified devices: {audit.total_qty} units."
        )

        messages.success(request, f"Audit session for {loc.name} successfully saved!")
        return redirect('audit_detail', audit_id=audit.id)

    # Pre-fill data if editing
    existing_items = {}
    if audit:
        for itm in audit.items.all():
            existing_items[itm.device_type_id] = {
                'active': itm.active_qty,
                'backup': itm.backup_qty,
                'faulty': itm.faulty_qty,
                'total': itm.total_qty,
                'remarks': itm.remarks or ''
            }

    context = {
        'audit': audit,
        'locations': eligible_locations,
        'selected_location_id': selected_location_id,
        'categories': categories,
        'existing_items': existing_items,
        'today': date.today().isoformat()
    }
    return render(request, 'audits/audit_form.html', context)



