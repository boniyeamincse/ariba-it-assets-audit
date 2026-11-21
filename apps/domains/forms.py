from django import forms
from .models import DomainRecord


class DomainRecordForm(forms.ModelForm):
    class Meta:
        model = DomainRecord
        fields = [
            'domain_name', 'company', 'category', 'registrar',
            'registrar_account_email', 'invoice_number', 'annual_cost', 'currency',
            'registration_date', 'expiry_date', 'auto_renewal',
            'dns_provider', 'primary_nameserver', 'secondary_nameserver',
            'primary_a_record_ip', 'hosting_provider', 'mail_provider',
            'ssl_status', 'ssl_provider', 'ssl_expiry_date',
            'status', 'technical_contact', 'remarks',
        ]
        widgets = {
            'registration_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'ssl_expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_domain_name(self):
        domain = self.cleaned_data['domain_name'].strip().lower()
        if domain.startswith('http://') or domain.startswith('https://'):
            domain = domain.split('://', 1)[1]
        domain = domain.split('/', 1)[0]
        return domain
