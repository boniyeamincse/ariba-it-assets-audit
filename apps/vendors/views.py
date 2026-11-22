from datetime import date, timedelta
from decimal import Decimal
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, roles_required, role_for
from apps.common.utils import log_activity
from apps.devices.models import Asset
from apps.locations.models import Location
from .forms import (
    VendorContactForm, VendorContractForm,
    VendorDocumentForm, VendorEvaluationForm, VendorFilterForm,
    VendorForm, VendorRMAForm
)
from .models import (
    Vendor, VendorContact, VendorContract, VendorDocument,
    VendorEvaluation, VendorRMA
)


# -----------------------------------------------------------------------------
# 1. Vendor Directory Views
# -----------------------------------------------------------------------------

@roles_required(*DASHBOARD_ROUTES)
@require_safe
def vendor_list_view(request):
    """
    Searchable, filterable list of all IT vendors and suppliers.
    """
    vendors = Vendor.objects.annotate(
        active_contracts_count=Count('contracts', filter=Q(contracts__status='ACTIVE')),
        supplied_assets_count=Count('supplied_assets'),
        open_rma_count=Count('rma_claims', filter=~Q(rma_claims__status__in=['RETURNED', 'CLOSED'])),
    ).order_by('name')

    filter_form = VendorFilterForm(request.GET)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        category = filter_form.cleaned_data.get('category')
        status = filter_form.cleaned_data.get('status')

        if q:
            vendors = vendors.filter(
                Q(name__icontains=q) |
                Q(vendor_code__icontains=q) |
                Q(bin_tin_number__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q)
            )
        if category:
            vendors = vendors.filter(category=category)
        if status:
            vendors = vendors.filter(status=status)

    # Summary Metrics
    total_vendors = Vendor.objects.count()
    active_vendors = Vendor.objects.filter(status='ACTIVE').count()
    active_contracts = VendorContract.objects.filter(status='ACTIVE').count()
    open_rmas = VendorRMA.objects.exclude(status__in=['RETURNED', 'CLOSED']).count()

    paginator = Paginator(vendors, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    can_edit = role_for(request.user) in CENTRAL_ROLES

    return render(request, 'vendors/vendor_list.html', {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'active_contracts': active_contracts,
        'open_rmas': open_rmas,
        'can_edit': can_edit,
    })


@roles_required(*CENTRAL_ROLES)
def vendor_create_view(request):
    """
    Create a new Vendor master record.
    """
    if request.method == 'POST':
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            log_activity(request, "CREATE", "Vendors", f"Created vendor '{vendor.name}' ({vendor.vendor_code})")
            messages.success(request, f"Vendor '{vendor.name}' created successfully with code {vendor.vendor_code}.")
            return redirect('vendor_detail', pk=vendor.pk)
    else:
        form = VendorForm()

    return render(request, 'vendors/vendor_form.html', {
        'form': form,
        'title': 'Add New Vendor / Supplier',
        'is_edit': False,
    })


@roles_required(*CENTRAL_ROLES)
def vendor_update_view(request, pk):
    """
    Edit existing Vendor master record.
    """
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method == 'POST':
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            vendor = form.save()
            log_activity(request, "UPDATE", "Vendors", f"Updated vendor '{vendor.name}' ({vendor.vendor_code})")
            messages.success(request, f"Vendor '{vendor.name}' updated successfully.")
            return redirect('vendor_detail', pk=vendor.pk)
    else:
        form = VendorForm(instance=vendor)

    return render(request, 'vendors/vendor_form.html', {
        'form': form,
        'vendor': vendor,
        'title': f'Edit Vendor: {vendor.name}',
        'is_edit': True,
    })


@roles_required(*DASHBOARD_ROUTES)
@require_safe
def vendor_detail_view(request, pk):
    """
    Comprehensive multi-tab profile of a vendor:
    - Overview & Contacts
    - Contracts & AMCs
    - Supplied Assets
    - RMA & Repair Tickets
    - Performance Scorecards
    - Document Attachments
    """
    vendor = get_object_or_404(Vendor, pk=pk)
    contacts = vendor.contacts.all().order_by('-is_primary', 'name')
    contracts = vendor.contracts.all().order_by('-end_date')
    rma_claims = vendor.rma_claims.select_related('asset', 'location').order_by('-dispatch_date')
    evaluations = vendor.evaluations.select_related('evaluated_by').order_by('-created_at')
    documents = vendor.documents.all().order_by('-created_at')

    # Supplied Assets: either via foreign key or text match
    supplied_assets = Asset.objects.filter(
        Q(vendor_ref=vendor) | Q(vendor__iexact=vendor.name)
    ).select_related('location', 'device_type').distinct().order_by('asset_tag')

    can_edit = role_for(request.user) in CENTRAL_ROLES

    # Sub-forms for modals / inline additions
    contact_form = VendorContactForm()
    evaluation_form = VendorEvaluationForm()
    document_form = VendorDocumentForm()

    return render(request, 'vendors/vendor_detail.html', {
        'vendor': vendor,
        'contacts': contacts,
        'contracts': contracts,
        'supplied_assets': supplied_assets,
        'rma_claims': rma_claims,
        'evaluations': evaluations,
        'documents': documents,
        'can_edit': can_edit,
        'contact_form': contact_form,
        'evaluation_form': evaluation_form,
        'document_form': document_form,
    })


@roles_required(*CENTRAL_ROLES)
@require_POST
def vendor_delete_view(request, pk):
    """
    Delete vendor profile if no critical dependencies exist.
    """
    vendor = get_object_or_404(Vendor, pk=pk)
    if vendor.contracts.exists() or vendor.supplied_assets.exists():
        messages.error(request, f"Cannot delete '{vendor.name}' because it has active contracts or assets attached.")
        return redirect('vendor_detail', pk=vendor.pk)
    name = vendor.name
    vendor.delete()
    log_activity(request, "DELETE", "Vendors", f"Deleted vendor '{name}'")
    messages.success(request, f"Vendor '{name}' has been deleted.")
    return redirect('vendor_list')


# -----------------------------------------------------------------------------
# 2. Vendor Contacts
# -----------------------------------------------------------------------------

@roles_required(*CENTRAL_ROLES)
@require_POST
def vendor_contact_add_view(request, vendor_pk):
    """
    Add contact person to a vendor.
    """
    vendor = get_object_or_404(Vendor, pk=vendor_pk)
    form = VendorContactForm(request.POST)
    if form.is_valid():
        contact = form.save(commit=False)
        contact.vendor = vendor
        contact.save()
        log_activity(request, "CREATE", "Vendors", f"Added contact '{contact.name}' to vendor '{vendor.name}'")
        messages.success(request, f"Contact person '{contact.name}' added.")
    else:
        messages.error(request, "Failed to add contact. Please review form fields.")
    return redirect('vendor_detail', pk=vendor.pk)


@roles_required(*CENTRAL_ROLES)
@require_POST
def vendor_contact_delete_view(request, pk):
    """
    Remove contact person from a vendor.
    """
    contact = get_object_or_404(VendorContact, pk=pk)
    vendor_pk = contact.vendor_id
    contact.delete()
    messages.success(request, "Contact removed.")
    return redirect('vendor_detail', pk=vendor_pk)


# -----------------------------------------------------------------------------
# 3. Contract & AMC Management
# -----------------------------------------------------------------------------

@roles_required(*DASHBOARD_ROUTES)
@require_safe
def contract_list_view(request):
    """
    List of all vendor contracts, AMCs, SLAs, and warranties.
    """
    today = date.today()
    contracts = VendorContract.objects.select_related('vendor').prefetch_related('covered_assets').order_by('end_date')

    # Filters
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    contract_type = request.GET.get('type', '').strip()

    if q:
        contracts = contracts.filter(
            Q(contract_number__icontains=q) |
            Q(title__icontains=q) |
            Q(vendor__name__icontains=q)
        )
    if status:
        contracts = contracts.filter(status=status)
    if contract_type:
        contracts = contracts.filter(contract_type=contract_type)

    # Metrics
    total_contracts = VendorContract.objects.count()
    active_contracts = VendorContract.objects.filter(status='ACTIVE', end_date__gte=today).count()
    expiring_soon = VendorContract.objects.filter(
        status='ACTIVE',
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30)
    ).count()
    expired = VendorContract.objects.filter(end_date__lt=today).count()

    paginator = Paginator(contracts, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'vendors/contract_list.html', {
        'page_obj': page_obj,
        'total_contracts': total_contracts,
        'active_contracts': active_contracts,
        'expiring_soon': expiring_soon,
        'expired': expired,
        'can_edit': role_for(request.user) in CENTRAL_ROLES,
        'q': q,
        'status': status,
        'contract_type': contract_type,
        'CONTRACT_TYPE_CHOICES': VendorContract.CONTRACT_TYPE_CHOICES,
        'STATUS_CHOICES': VendorContract.STATUS_CHOICES,
    })


@roles_required(*CENTRAL_ROLES)
def contract_create_view(request):
    """
    Create a new AMC or Contract.
    """
    vendor_id = request.GET.get('vendor')
    initial = {}
    if vendor_id:
        initial['vendor'] = vendor_id

    if request.method == 'POST':
        form = VendorContractForm(request.POST, request.FILES)
        if form.is_valid():
            contract = form.save()
            log_activity(request, "CREATE", "Vendors", f"Created contract '{contract.contract_number}' for vendor '{contract.vendor.name}'")
            messages.success(request, f"Contract '{contract.contract_number}' registered successfully.")
            return redirect('contract_detail', pk=contract.pk)
    else:
        form = VendorContractForm(initial=initial)

    return render(request, 'vendors/contract_form.html', {
        'form': form,
        'title': 'Register New Contract / AMC',
        'is_edit': False,
    })


@roles_required(*CENTRAL_ROLES)
def contract_update_view(request, pk):
    """
    Update existing contract or AMC.
    """
    contract = get_object_or_404(VendorContract, pk=pk)
    if request.method == 'POST':
        form = VendorContractForm(request.POST, request.FILES, instance=contract)
        if form.is_valid():
            contract = form.save()
            log_activity(request, "UPDATE", "Vendors", f"Updated contract '{contract.contract_number}'")
            messages.success(request, f"Contract '{contract.contract_number}' updated successfully.")
            return redirect('contract_detail', pk=contract.pk)
    else:
        form = VendorContractForm(instance=contract)

    return render(request, 'vendors/contract_form.html', {
        'form': form,
        'contract': contract,
        'title': f'Edit Contract: {contract.contract_number}',
        'is_edit': True,
    })


@roles_required(*DASHBOARD_ROUTES)
@require_safe
def contract_detail_view(request, pk):
    """
    Detail view of a specific contract or AMC.
    """
    contract = get_object_or_404(VendorContract.objects.select_related('vendor'), pk=pk)
    covered_assets = contract.covered_assets.select_related('location', 'device_type').order_by('asset_tag')
    can_edit = role_for(request.user) in CENTRAL_ROLES

    return render(request, 'vendors/contract_detail.html', {
        'contract': contract,
        'covered_assets': covered_assets,
        'can_edit': can_edit,
    })


# -----------------------------------------------------------------------------
# 4. RMA & Warranty Claim Management
# -----------------------------------------------------------------------------

@roles_required(*DASHBOARD_ROUTES)
@require_safe
def rma_list_view(request):
    """
    List of RMA tickets, warranty claims, and repairs.
    """
    claims = VendorRMA.objects.select_related('vendor', 'asset', 'location', 'logged_by').order_by('-dispatch_date')

    # Filter
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if q:
        claims = claims.filter(
            Q(rma_number__icontains=q) |
            Q(asset__asset_tag__icontains=q) |
            Q(asset__serial_number__icontains=q) |
            Q(vendor__name__icontains=q)
        )
    if status:
        claims = claims.filter(status=status)

    open_claims = VendorRMA.objects.exclude(status__in=['RETURNED', 'CLOSED']).count()
    standby_deployed = VendorRMA.objects.filter(standby_provided=True).exclude(status__in=['RETURNED', 'CLOSED']).count()
    resolved_claims = VendorRMA.objects.filter(status__in=['RETURNED', 'CLOSED']).count()

    paginator = Paginator(claims, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'vendors/rma_list.html', {
        'page_obj': page_obj,
        'open_claims': open_claims,
        'standby_deployed': standby_deployed,
        'resolved_claims': resolved_claims,
        'q': q,
        'status': status,
        'RMA_STATUS_CHOICES': VendorRMA.RMA_STATUS_CHOICES,
    })


@roles_required(*DASHBOARD_ROUTES)
def rma_create_view(request):
    """
    Log a new RMA / Warranty claim.
    """
    asset_id = request.GET.get('asset')
    vendor_id = request.GET.get('vendor')
    initial = {}
    if asset_id:
        initial['asset'] = asset_id
    if vendor_id:
        initial['vendor'] = vendor_id

    if request.method == 'POST':
        form = VendorRMAForm(request.POST)
        if form.is_valid():
            rma = form.save(commit=False)
            rma.logged_by = request.user
            rma.save()
            log_activity(request, "CREATE", "Vendors", f"Logged RMA claim '{rma.rma_number}' for asset '{rma.asset.asset_tag}'")
            messages.success(request, f"RMA claim '{rma.rma_number}' logged successfully.")
            return redirect('rma_list')
    else:
        form = VendorRMAForm(initial=initial)

    return render(request, 'vendors/rma_form.html', {
        'form': form,
        'title': 'Log RMA / Warranty Claim',
        'is_edit': False,
    })


@roles_required(*DASHBOARD_ROUTES)
def rma_update_view(request, pk):
    """
    Update RMA / Warranty claim progress or resolution.
    """
    rma = get_object_or_404(VendorRMA, pk=pk)
    if request.method == 'POST':
        form = VendorRMAForm(request.POST, instance=rma)
        if form.is_valid():
            rma = form.save()
            log_activity(request, "UPDATE", "Vendors", f"Updated RMA claim '{rma.rma_number}' status to '{rma.get_status_display()}'")
            messages.success(request, f"RMA claim '{rma.rma_number}' updated.")
            return redirect('rma_list')
    else:
        form = VendorRMAForm(instance=rma)

    return render(request, 'vendors/rma_form.html', {
        'form': form,
        'rma': rma,
        'title': f'Update RMA Claim: {rma.rma_number}',
        'is_edit': True,
    })


# -----------------------------------------------------------------------------
# 5. Vendor Evaluations & Documents
# -----------------------------------------------------------------------------

@roles_required(*DASHBOARD_ROUTES)
@require_POST
def vendor_evaluation_create_view(request, vendor_pk):
    """
    Submit performance scorecard for a vendor.
    """
    vendor = get_object_or_404(Vendor, pk=vendor_pk)
    form = VendorEvaluationForm(request.POST)
    if form.is_valid():
        eval_record = form.save(commit=False)
        eval_record.vendor = vendor
        eval_record.evaluated_by = request.user
        eval_record.save()
        log_activity(request, "CREATE", "Vendors", f"Submitted performance evaluation for vendor '{vendor.name}' (Score: {eval_record.composite_score})")
        messages.success(request, f"Evaluation recorded with composite score {eval_record.composite_score}/5.00.")
    else:
        messages.error(request, "Failed to save evaluation. Please check your ratings.")
    return redirect('vendor_detail', pk=vendor.pk)


@roles_required(*CENTRAL_ROLES)
@require_POST
def vendor_document_upload_view(request, vendor_pk):
    """
    Upload compliance document or agreement to vendor profile.
    """
    vendor = get_object_or_404(Vendor, pk=vendor_pk)
    form = VendorDocumentForm(request.POST, request.FILES)
    if form.is_valid():
        doc = form.save(commit=False)
        doc.vendor = vendor
        doc.save()
        log_activity(request, "CREATE", "Vendors", f"Uploaded document '{doc.title}' for vendor '{vendor.name}'")
        messages.success(request, f"Document '{doc.title}' uploaded successfully.")
    else:
        messages.error(request, "Failed to upload document. Please verify the file format.")
    return redirect('vendor_detail', pk=vendor.pk)


# -----------------------------------------------------------------------------
# 6. Excel Exports
# -----------------------------------------------------------------------------

@roles_required(*DASHBOARD_ROUTES)
@require_safe
def export_vendors_excel(request):
    """
    Export vendor master directory to Excel.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vendors Directory"

    headers = [
        "Vendor Code", "Company Name", "Category", "Status",
        "Overall Rating", "Email", "Phone", "BIN / TIN",
        "Trade License", "City", "Active Contracts", "Covered Assets"
    ]
    ws.append(headers)

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    vendors = Vendor.objects.annotate(
        active_contracts_count=Count('contracts', filter=Q(contracts__status='ACTIVE')),
        supplied_assets_count=Count('supplied_assets')
    ).order_by('name')

    for v in vendors:
        ws.append([
            v.vendor_code,
            v.name,
            v.get_category_display(),
            v.get_status_display(),
            float(v.overall_rating),
            v.email or "-",
            v.phone or "-",
            v.bin_tin_number or "-",
            v.trade_license_no or "-",
            v.city or "-",
            v.active_contracts_count,
            v.supplied_assets_count,
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename="Vendor_Directory_Akij_Group.xlsx"'
    wb.save(response)
    return response
