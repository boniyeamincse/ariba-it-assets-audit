from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, JsonResponse, HttpResponse
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from datetime import date
import json

from apps.locations.models import Location
from apps.devices.models import DeviceCategory, DeviceType
from apps.audits.models import AuditSession, AuditItem
from apps.common.utils import log_activity
from apps.accounts.access import DASHBOARD_ROUTES, LOCAL_TYPES, role_for, roles_required, visible_locations

@roles_required(*DASHBOARD_ROUTES)
def audit_list_view(request):
    """
    List of all audit sessions across Head Office, Factories, and Depots.
    """
    locations = visible_locations(request.user)
    audits = AuditSession.objects.filter(location__in=locations).select_related('location').order_by('-audit_date', '-created_at')
    context = {
        'audits': audits,
        'locations': locations,
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


@roles_required(*DASHBOARD_ROUTES)
def export_audit_json(request, audit_id):
    """
    Export single audit session as a structured JSON file.
    """
    audit = get_object_or_404(AuditSession, id=audit_id, location__in=visible_locations(request.user))
    data = audit.to_dict()
    filename = f"audit_{audit.location.code}_{audit.audit_date}.json"

    log_activity(
        request=request,
        action='EXPORT_JSON',
        module='Audits',
        description=f"Exported offline JSON audit file for {audit.location.name} ({audit.audit_date})."
    )

    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type="application/json"
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@roles_required(*DASHBOARD_ROUTES)
def sync_json_view(request):
    """
    Upload and import offline JSON audit file from field laptops.
    """
    role = role_for(request.user)
    local_admin = role in LOCAL_TYPES
    if request.method == 'POST' and request.FILES.get('json_file'):
        try:
            uploaded_file = request.FILES['json_file']
            content = json.loads(uploaded_file.read().decode('utf-8'))

            loc_name = content.get('location')
            audit_date = content.get('auditDate', str(date.today()))
            auditor = content.get('auditedBy', 'IT Audit Team')
            verified = content.get('verifiedBy', '')
            status = content.get('status', 'APPROVED')

            locations = visible_locations(request.user)
            if local_admin:
                code = content.get('location_code')
                matching = locations.filter(code=code) if code else locations.filter(name=loc_name)
                try:
                    loc = matching.get()
                except (Location.DoesNotExist, Location.MultipleObjectsReturned):
                    messages.error(request, 'Select an assigned location using its exact code or name.')
                    return render(request, 'audits/sync_json.html', status=400)
                status = 'DRAFT'
                auditor = request.user.get_full_name() or request.user.username
                verified = ''
            else:
                loc = locations.filter(name__icontains=loc_name).first()
            if loc is None:
                company = Location.objects.first().company
                loc = Location.objects.create(
                    company=company,
                    name=loc_name,
                    code=loc_name.upper().replace(' ', '-'),
                    location_type='FACTORY'
                )

            with transaction.atomic():
                parsed_date = date.fromisoformat(audit_date)
                defaults = {'auditor_name': auditor, 'verified_by_name': verified, 'status': status}
                if local_admin:
                    audit, created = AuditSession.objects.select_for_update().get_or_create(
                        location=loc, audit_date=parsed_date, defaults=defaults,
                    )
                    if audit.status != 'DRAFT':
                        raise PermissionDenied
                    if not created:
                        audit.auditor_name = auditor
                        audit.verified_by_name = verified
                        audit.save(update_fields=['auditor_name', 'verified_by_name', 'updated_at'])
                else:
                    audit, _ = AuditSession.objects.update_or_create(
                        location=loc, audit_date=parsed_date, defaults=defaults,
                    )

                # Process infrastructure
                for item in content.get('infrastructure', []):
                    d_name = item.get('device')
                    qty = int(item.get('qty', 0))
                    dev = DeviceType.objects.filter(name__iexact=d_name).first()
                    if dev:
                        AuditItem.objects.update_or_create(
                            audit_session=audit,
                            device_type=dev,
                            defaults={
                                'active_qty': qty,
                                'backup_qty': 0,
                                'faulty_qty': 0,
                                'total_qty': qty,
                                'remarks': item.get('remarks', '')
                            }
                        )

                # Process users
                for item in content.get('users', []):
                    d_name = item.get('device')
                    qty = int(item.get('qty', 0))
                    act = int(item.get('active', qty))
                    bak = int(item.get('backup', 0))
                    flt = int(item.get('faulty', 0))
                    dev = DeviceType.objects.filter(name__iexact=d_name).first()
                    if dev:
                        AuditItem.objects.update_or_create(
                            audit_session=audit,
                            device_type=dev,
                            defaults={
                                'active_qty': act,
                                'backup_qty': bak,
                                'faulty_qty': flt,
                                'total_qty': act + bak + flt,
                                'remarks': item.get('remarks', '')
                            }
                        )

            log_activity(
                request=request,
                action='IMPORT_JSON',
                module='Audits',
                description=f"Imported offline JSON audit for {loc.name} on {audit.audit_date}. Total verified devices: {audit.total_qty} units."
            )

            messages.success(request, f"Successfully imported audit data for {loc.name}!")
            return redirect('audit_detail', audit_id=audit.id)
        except PermissionDenied:
            raise
        except Exception as e:
            messages.error(request, f"Error importing JSON: {str(e)}")

    return render(request, 'audits/sync_json.html')
