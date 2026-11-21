from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.access import CENTRAL_ROLES, roles_required
from apps.locations.models import Company
from apps.common.utils import log_activity
from .models import DomainRecord
from .forms import DomainRecordForm


def _filter_domains(request):
    """
    Shared filtering logic for domain list view and Excel export.
    """
    domain_qs = DomainRecord.objects.select_related('company').all()

    company_filter = request.GET.get('company', '').strip()
    category_filter = request.GET.get('category', '').strip()
    registrar_filter = request.GET.get('registrar', '').strip()
    status_filter = request.GET.get('status', '').strip()
    ssl_filter = request.GET.get('ssl', '').strip()
    auto_renew_filter = request.GET.get('auto_renew', '').strip()
    expiry_range = request.GET.get('expiry_range', '').strip()
    search_query = request.GET.get('q', '').strip()

    if company_filter:
        domain_qs = domain_qs.filter(company_id=company_filter)

    if category_filter:
        domain_qs = domain_qs.filter(category=category_filter)

    if registrar_filter:
        domain_qs = domain_qs.filter(registrar=registrar_filter)

    if status_filter:
        domain_qs = domain_qs.filter(status=status_filter)

    today = timezone.now().date()
    if ssl_filter == 'issues':
        domain_qs = domain_qs.filter(
            Q(ssl_status__in=['EXPIRING_SOON', 'EXPIRED']) |
            Q(ssl_expiry_date__lte=today + timedelta(days=30), ssl_expiry_date__isnull=False)
        )
    elif ssl_filter:
        domain_qs = domain_qs.filter(ssl_status=ssl_filter)

    if auto_renew_filter == 'yes':
        domain_qs = domain_qs.filter(auto_renewal=True)
    elif auto_renew_filter == 'no':
        domain_qs = domain_qs.filter(auto_renewal=False)

    if expiry_range == 'expired':
        domain_qs = domain_qs.filter(expiry_date__lt=today)
    elif expiry_range == 'expiring_30':
        domain_qs = domain_qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30))
    elif expiry_range == 'expiring_60':
        domain_qs = domain_qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=60))
    elif expiry_range == 'expiring_90':
        domain_qs = domain_qs.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=90))

    if search_query:
        domain_qs = domain_qs.filter(
            Q(domain_name__icontains=search_query) |
            Q(primary_a_record_ip__icontains=search_query) |
            Q(primary_nameserver__icontains=search_query) |
            Q(secondary_nameserver__icontains=search_query) |
            Q(technical_contact__icontains=search_query) |
            Q(registrar_account_email__icontains=search_query) |
            Q(invoice_number__icontains=search_query) |
            Q(hosting_provider__icontains=search_query)
        )

    filters = {
        'company_filter': company_filter,
        'category_filter': category_filter,
        'registrar_filter': registrar_filter,
        'status_filter': status_filter,
        'ssl_filter': ssl_filter,
        'auto_renew_filter': auto_renew_filter,
        'expiry_range': expiry_range,
        'search_query': search_query,
    }
    return domain_qs, filters


@roles_required(*CENTRAL_ROLES)
def domain_list_view(request):
    """
    Central Domain, DNS & SSL Certificate Management Directory.
    Provides multi-company governance, expiry countdowns, registrar tracking, and SSL monitoring.
    """
    domain_qs, filters = _filter_domains(request)
    today = timezone.now().date()

    # Global KPI metrics across all domains
    all_domains = DomainRecord.objects.all()
    total_domains = all_domains.count()
    expired_count = all_domains.filter(expiry_date__lt=today).count()
    expiring_30_count = all_domains.filter(
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=30)
    ).count()
    ssl_expiring_count = all_domains.filter(
        Q(ssl_status__in=['EXPIRING_SOON', 'EXPIRED']) |
        Q(ssl_expiry_date__lte=today + timedelta(days=30), ssl_expiry_date__isnull=False)
    ).count()
    active_count = all_domains.filter(status='ACTIVE', expiry_date__gte=today).count()
    auto_renew_count = all_domains.filter(auto_renewal=True).count()
    auto_renew_pct = round((auto_renew_count / total_domains * 100), 1) if total_domains > 0 else 0

    # Companies for filter
    companies = Company.objects.filter(is_active=True).order_by('name')

    # Pagination
    paginator = Paginator(domain_qs.order_by('expiry_date', 'domain_name'), 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    has_active_filters = any([
        filters['company_filter'],
        filters['category_filter'],
        filters['registrar_filter'],
        filters['status_filter'],
        filters['ssl_filter'],
        filters['auto_renew_filter'],
        filters['expiry_range'],
        filters['search_query'],
    ])

    context = {
        'page_obj': page_obj,
        'total_domains': total_domains,
        'filtered_count': domain_qs.count(),
        'expired_count': expired_count,
        'expiring_30_count': expiring_30_count,
        'ssl_expiring_count': ssl_expiring_count,
        'active_count': active_count,
        'auto_renew_pct': auto_renew_pct,
        'companies': companies,
        'has_active_filters': has_active_filters,
        **filters,
        'category_choices': DomainRecord.CATEGORY_CHOICES,
        'registrar_choices': DomainRecord.REGISTRAR_CHOICES,
        'status_choices': DomainRecord.STATUS_CHOICES,
        'ssl_status_choices': DomainRecord.SSL_STATUS_CHOICES,
    }
    return render(request, 'domains/domain_list.html', context)


@roles_required(*CENTRAL_ROLES)
def domain_export_excel(request):
    """
    Exports filtered or complete domain records to an Excel spreadsheet with full metadata.
    """
    domain_qs, _ = _filter_domains(request)
    domain_qs = domain_qs.order_by('expiry_date', 'domain_name')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Domain_Governance_Register"

    # Styling
    hdr_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    hdr_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')

    # Title Banner
    ws.append(['Akij Group - Corporate Domain, DNS & SSL Governance Register'])
    ws.cell(row=1, column=1).font = Font(name='Calibri', size=14, bold=True, color='1F4E78')
    ws.append([f'Generated on: {timezone.now().strftime("%Y-%m-%d %H:%M")} | Total Exported Records: {domain_qs.count()}'])
    ws.cell(row=2, column=1).font = Font(name='Calibri', size=10, italic=True, color='595959')
    ws.append([])  # blank row

    headers = [
        'SL', 'Domain Name', 'Owning Company', 'Classification',
        'Registrar', 'Registrar Email', 'Invoice / PO', 'Annual Cost', 'Currency',
        'Registration Date', 'Expiry Date', 'Days to Expiry', 'Status', 'Auto-Renew',
        'DNS Provider', 'Primary NS', 'Secondary NS', 'Server IP', 'Hosting Provider',
        'Mail Provider', 'SSL Status', 'SSL Provider', 'SSL Expiry Date',
        'IT In-Charge', 'Remarks'
    ]
    ws.append(headers)

    header_row = 4
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = center_align
        cell.border = border

    for idx, dom in enumerate(domain_qs, start=1):
        row = [
            idx,
            dom.domain_name,
            dom.company.name if dom.company else '',
            dom.get_category_display(),
            dom.get_registrar_display(),
            dom.registrar_account_email or '',
            dom.invoice_number or '',
            float(dom.annual_cost),
            dom.currency,
            dom.registration_date.strftime("%Y-%m-%d") if dom.registration_date else '',
            dom.expiry_date.strftime("%Y-%m-%d") if dom.expiry_date else '',
            dom.days_until_expiry,
            dom.get_status_display(),
            'Yes' if dom.auto_renewal else 'No',
            dom.get_dns_provider_display(),
            dom.primary_nameserver or '',
            dom.secondary_nameserver or '',
            dom.primary_a_record_ip or '',
            dom.hosting_provider or '',
            dom.get_mail_provider_display(),
            dom.get_ssl_status_display(),
            dom.ssl_provider or '',
            dom.ssl_expiry_date.strftime("%Y-%m-%d") if dom.ssl_expiry_date else '',
            dom.technical_contact or '',
            dom.remarks or ''
        ]
        ws.append(row)
        current_row = header_row + idx
        for col_idx in range(1, len(row) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = border
            cell.font = Font(name='Calibri', size=10)
            if col_idx in (1, 8, 9, 10, 11, 12, 13, 14, 18, 23):
                cell.alignment = center_align
            else:
                cell.alignment = left_align

    # Auto-fit column widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

    log_activity(
        request=request,
        action='EXPORT_EXCEL',
        module='Domains',
        description=f"Exported {domain_qs.count()} domain records to Excel spreadsheet."
    )

    filename = f"Akij_Domains_Registry_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@roles_required(*CENTRAL_ROLES)
def domain_create_or_edit_view(request, pk=None):
    """
    Register a new corporate domain or modify existing DNS, registrar, and SSL settings.
    """
    domain = get_object_or_404(DomainRecord, pk=pk) if pk else None

    if request.method == 'POST':
        form = DomainRecordForm(request.POST, instance=domain)
        if form.is_valid():
            saved_domain = form.save()
            action = 'UPDATE_DOMAIN' if domain else 'CREATE_DOMAIN'
            log_activity(
                request=request,
                action=action,
                module='Domains',
                description=f"{'Updated' if domain else 'Registered'} domain record [{saved_domain.domain_name}] for {saved_domain.company.name}."
            )
            messages.success(
                request,
                f"Domain '{saved_domain.domain_name}' successfully {'updated' if domain else 'registered'}!"
            )
            return redirect('domain_list')
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        form = DomainRecordForm(instance=domain)

    companies = Company.objects.filter(is_active=True).order_by('name')
    context = {
        'form': form,
        'domain': domain,
        'companies': companies,
        'category_choices': DomainRecord.CATEGORY_CHOICES,
        'registrar_choices': DomainRecord.REGISTRAR_CHOICES,
        'dns_choices': DomainRecord.DNS_PROVIDER_CHOICES,
        'mail_choices': DomainRecord.MAIL_PROVIDER_CHOICES,
        'ssl_choices': DomainRecord.SSL_STATUS_CHOICES,
        'status_choices': DomainRecord.STATUS_CHOICES,
    }
    return render(request, 'domains/domain_form.html', context)


@roles_required(*CENTRAL_ROLES)
def domain_detail_view(request, pk):
    """
    View complete technical specifications, DNS records, SSL certificates, and lifecycle details of a domain.
    """
    domain = get_object_or_404(DomainRecord.objects.select_related('company'), pk=pk)
    return render(request, 'domains/domain_detail.html', {'domain': domain})


@roles_required(*CENTRAL_ROLES)
def domain_delete_view(request, pk):
    """
    Delete a domain record from the system with activity logging.
    """
    domain = get_object_or_404(DomainRecord, pk=pk)
    if request.method == 'POST':
        name = domain.domain_name
        company_name = domain.company.name
        domain.delete()
        log_activity(
            request=request,
            action='DELETE_DOMAIN',
            module='Domains',
            description=f"Deleted domain record [{name}] of {company_name}."
        )
        messages.success(request, f"Domain record '{name}' has been deleted.")
        return redirect('domain_list')

    return render(request, 'domains/domain_confirm_delete.html', {'domain': domain})
