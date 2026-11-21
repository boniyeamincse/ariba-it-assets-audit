from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from apps.accounts.access import CENTRAL_ROLES, roles_required
from apps.locations.models import Company
from apps.common.utils import log_activity
from .models import DomainRecord
from .forms import DomainRecordForm


@login_required
def domain_list_view(request):
    """
    Central Domain, DNS & SSL Certificate Management Directory.
    Provides multi-company governance, expiry countdowns, registrar tracking, and SSL monitoring.
    """
    domain_qs = DomainRecord.objects.select_related('company').all()

    # Filters
    company_filter = request.GET.get('company', '').strip()
    category_filter = request.GET.get('category', '').strip()
    registrar_filter = request.GET.get('registrar', '').strip()
    status_filter = request.GET.get('status', '').strip()
    ssl_filter = request.GET.get('ssl', '').strip()
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

    if ssl_filter:
        domain_qs = domain_qs.filter(ssl_status=ssl_filter)

    today = timezone.now().date()
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

    context = {
        'page_obj': page_obj,
        'total_domains': total_domains,
        'expired_count': expired_count,
        'expiring_30_count': expiring_30_count,
        'ssl_expiring_count': ssl_expiring_count,
        'active_count': active_count,
        'auto_renew_pct': auto_renew_pct,
        'companies': companies,
        'company_filter': company_filter,
        'category_filter': category_filter,
        'registrar_filter': registrar_filter,
        'status_filter': status_filter,
        'ssl_filter': ssl_filter,
        'expiry_range': expiry_range,
        'search_query': search_query,
        'category_choices': DomainRecord.CATEGORY_CHOICES,
        'registrar_choices': DomainRecord.REGISTRAR_CHOICES,
        'status_choices': DomainRecord.STATUS_CHOICES,
        'ssl_status_choices': DomainRecord.SSL_STATUS_CHOICES,
    }
    return render(request, 'domains/domain_list.html', context)


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


@login_required
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
