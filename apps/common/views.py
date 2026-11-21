from django.shortcuts import render
from django import forms
from django.core.paginator import Paginator
from django.db.models import Q
from apps.accounts.access import CENTRAL_ROLES, roles_required
from apps.common.models import SystemActivityLog, SystemSettings


class ActivityDateFilter(forms.Form):
    date_from = forms.DateField(label='From date', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(label='To date', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('date_from'), cleaned.get('date_to')
        if start and end and end < start:
            self.add_error('date_to', 'The end date must be on or after the start date.')
        return cleaned


@roles_required(*CENTRAL_ROLES)
def activity_log_view(request):
    """
    Enterprise System Activity & Audit Trail Log Viewer.
    Central administrators can inspect activity across locations.
    """
    logs_qs = SystemActivityLog.objects.order_by('-created_at', '-pk')

    # Filter parameters
    module_filter = request.GET.get('module', '').strip()
    action_filter = request.GET.get('action', '').strip()
    search_query = request.GET.get('q', '').strip()
    dates = ActivityDateFilter(request.GET)

    if module_filter:
        logs_qs = logs_qs.filter(module__iexact=module_filter)

    if action_filter:
        logs_qs = logs_qs.filter(action__iexact=action_filter)

    if search_query:
        logs_qs = logs_qs.filter(
            Q(user_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(action__icontains=search_query) |
            Q(ip_address__icontains=search_query)
        )

    if dates.is_valid():
        if dates.cleaned_data['date_from']:
            logs_qs = logs_qs.filter(created_at__date__gte=dates.cleaned_data['date_from'])
        if dates.cleaned_data['date_to']:
            logs_qs = logs_qs.filter(created_at__date__lte=dates.cleaned_data['date_to'])
    else:
        logs_qs = logs_qs.none()

    # Distinct modules and actions for filter dropdowns
    available_modules = SystemActivityLog.objects.values_list('module', flat=True).distinct()
    available_actions = SystemActivityLog.objects.values_list('action', flat=True).distinct()

    paginator = Paginator(logs_qs, SystemSettings.current().activity_page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_count': paginator.count,
        'module_filter': module_filter,
        'action_filter': action_filter,
        'search_query': search_query,
        'dates': dates,
        'available_modules': sorted(filter(None, available_modules)),
        'available_actions': sorted(filter(None, available_actions)),
    }
    return render(request, 'common/activity_logs.html', context)
