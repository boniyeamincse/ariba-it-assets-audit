from django import forms
from apps.devices.models import Asset
from apps.locations.models import Location
from .models import (
    Vendor, VendorContact, VendorContract, VendorRMA, VendorEvaluation, VendorDocument
)


class BaseStyledModelForm(forms.ModelForm):
    """
    Applies standard Tailwind form control styles to widgets.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500')
                widget.attrs.setdefault('rows', 3)
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100')
            else:
                widget.attrs.setdefault('class', 'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500')


class VendorForm(BaseStyledModelForm):
    class Meta:
        model = Vendor
        fields = [
            'name', 'vendor_code', 'category', 'status',
            'bin_tin_number', 'trade_license_no', 'vat_registration_no',
            'email', 'phone', 'helpline_number', 'website', 'support_portal_url',
            'address', 'city', 'country', 'credit_period_days', 'notes',
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'corporate@vendor.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+880 2-XXXXXXX'}),
            'helpline_number': forms.TextInput(attrs={'placeholder': 'Hotline: 16XXX or 096XXXXXXXX'}),
            'website': forms.URLInput(attrs={'placeholder': 'https://www.vendor.com'}),
            'support_portal_url': forms.URLInput(attrs={'placeholder': 'https://support.vendor.com'}),
            'address': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Full corporate office address'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Internal notes or historical remarks'}),
        }


class VendorContactForm(BaseStyledModelForm):
    class Meta:
        model = VendorContact
        fields = [
            'name', 'designation', 'contact_type',
            'email', 'phone', 'mobile', 'is_primary'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'person@vendor.com'}),
            'mobile': forms.TextInput(attrs={'placeholder': '+880 17XXXXXXXX'}),
        }


class VendorContractForm(BaseStyledModelForm):
    class Meta:
        model = VendorContract
        fields = [
            'vendor', 'contract_number', 'title', 'contract_type',
            'start_date', 'end_date', 'contract_value', 'currency',
            'payment_terms', 'sla_terms', 'status', 'auto_renew',
            'document', 'covered_assets',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'sla_terms': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Response times, penalty clauses, uptime commitments'}),
            'payment_terms': forms.TextInput(attrs={'placeholder': 'e.g. Quarterly in advance, Net 30'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['covered_assets'].queryset = Asset.objects.select_related('location', 'device_type').order_by('asset_tag', 'model_name')
        self.fields['covered_assets'].help_text = "Hold Ctrl (Windows) or Cmd (Mac) to select multiple assets."


class VendorRMAForm(BaseStyledModelForm):
    class Meta:
        model = VendorRMA
        fields = [
            'vendor', 'asset', 'location', 'rma_number',
            'issue_description', 'dispatch_date', 'expected_return_date',
            'actual_return_date', 'status', 'standby_provided',
            'replacement_serial_no', 'repair_cost', 'challan_reference',
            'resolution_notes',
        ]
        widgets = {
            'dispatch_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_return_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_return_date': forms.DateInput(attrs={'type': 'date'}),
            'issue_description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe symptoms, error codes, and physical damage'}),
            'resolution_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Diagnosis, parts replaced, vendor ticket ID'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = Asset.objects.select_related('location', 'device_type').order_by('asset_tag', 'model_name')
        self.fields['location'].queryset = Location.objects.order_by('name')


class VendorEvaluationForm(BaseStyledModelForm):
    class Meta:
        model = VendorEvaluation
        fields = [
            'review_period',
            'delivery_score', 'quality_score', 'support_score', 'pricing_score',
            'comments',
        ]
        widgets = {
            'delivery_score': forms.Select(choices=[(i, f"{i} - {['Very Poor', 'Poor', 'Satisfactory', 'Good', 'Excellent'][i-1]}") for i in range(1, 6)]),
            'quality_score': forms.Select(choices=[(i, f"{i} - {['Very Poor', 'Poor', 'Satisfactory', 'Good', 'Excellent'][i-1]}") for i in range(1, 6)]),
            'support_score': forms.Select(choices=[(i, f"{i} - {['Very Poor', 'Poor', 'Satisfactory', 'Good', 'Excellent'][i-1]}") for i in range(1, 6)]),
            'pricing_score': forms.Select(choices=[(i, f"{i} - {['Very Poor', 'Poor', 'Satisfactory', 'Good', 'Excellent'][i-1]}") for i in range(1, 6)]),
            'comments': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Detailed feedback on vendor performance'}),
        }


class VendorDocumentForm(BaseStyledModelForm):
    class Meta:
        model = VendorDocument
        fields = ['title', 'doc_type', 'file']


class VendorFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search vendor name, code, TIN or email...',
            'class': 'w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'
        })
    )
    category = forms.ChoiceField(
        choices=[('', 'All Categories'), *Vendor.CATEGORY_CHOICES],
        required=False,
        widget=forms.Select(attrs={'class': 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses'), *Vendor.STATUS_CHOICES],
        required=False,
        widget=forms.Select(attrs={'class': 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none'})
    )
