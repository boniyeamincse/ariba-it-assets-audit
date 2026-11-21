from django import forms
from django.utils.text import slugify

from apps.locations.models import Company, Location


class ParentLocationSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if hasattr(value, 'instance'):
            option['attrs']['data-company'] = value.instance.company_id
        return option


class ParentLocationField(forms.ModelChoiceField):
    def label_from_instance(self, location):
        return f'{location.name} · {location.company.short_code} ({location.location_id or location.code})'


class LocationForm(forms.ModelForm):
    code = forms.CharField(label='Location code', max_length=50, required=False)
    status = forms.ChoiceField(choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive')], required=False)
    parent_location = ParentLocationField(
        queryset=Location.objects.none(), required=False, widget=ParentLocationSelect,
    )

    class Meta:
        model = Location
        fields = [
            'name', 'company', 'location_type', 'location_id', 'code', 'parent_location',
            'status', 'address', 'city', 'division', 'contact_person', 'contact_number', 'description',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'contact_number': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
        }

    def __init__(self, *args, default_company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_company = default_company
        self.editing = self.instance.pk is not None
        self.initial['status'] = 'ACTIVE' if not self.editing or self.instance.is_active else 'INACTIVE'
        companies = Company.objects.filter(is_active=True)
        if self.editing:
            companies = Company.objects.filter(pk=self.instance.company_id)
        self.fields['company'].queryset = companies.order_by('name')
        self.fields['company'].required = False
        self.fields['company'].disabled = self.editing
        self.fields['company'].empty_label = 'Use default company'
        self.fields['location_type'].required = False
        if default_company and not self.editing:
            self.initial['company'] = default_company.pk
            self.fields['company'].widget.attrs['data-default-company'] = default_company.pk
        parents = Location.objects.filter(is_active=True)
        if self.editing:
            parents = Location.objects.filter(company_id=self.instance.company_id)
            parents = parents.exclude(pk=self.instance.pk)
        self.fields['parent_location'].queryset = parents.select_related('company').order_by('company__name', 'name', 'pk')
        self.fields['code'].disabled = self.editing
        self.fields['code'].help_text = (
            'Used by imports and reports.' if self.editing else 'Leave blank to generate a unique code from the location name.'
        )
        self.fields['location_id'].help_text = 'Leave blank to use the assigned ID.'

    @property
    def sections(self):
        groups = (
            ('Location details', ('name', 'company', 'location_type', 'location_id', 'code', 'status', 'parent_location')),
            ('Address', ('address', 'city', 'division')),
            ('Contact & notes', ('contact_person', 'contact_number', 'description')),
        )
        return [(title, [self[name] for name in fields]) for title, fields in groups]

    def clean_company(self):
        return self.cleaned_data['company'] or self.default_company

    def clean_location_id(self):
        value = (self.cleaned_data['location_id'] or '').upper()
        return value or self.instance.location_id

    def clean_location_type(self):
        return self.cleaned_data['location_type'] or self.instance.location_type

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('code')
        if code:
            cleaned['code'] = code if self.editing else code.upper()
        elif 'code' in cleaned and cleaned.get('name'):
            prefix = slugify(cleaned['name'], allow_unicode=True).upper()[:35].strip('-') or 'LOCATION'
            candidate = prefix
            for suffix in range(2, Location.objects.count() + 3):
                if not Location.objects.filter(code=candidate).exists():
                    break
                candidate = f'{prefix}-{suffix}'
            cleaned['code'] = candidate

        parent = cleaned.get('parent_location')
        company = cleaned.get('company')
        if parent and (not company or parent.company_id != company.pk):
            self.add_error('parent_location', 'Select a parent in the same company.')
        elif parent:
            visited = {self.instance.pk}
            while parent:
                if parent.pk in visited:
                    self.add_error('parent_location', 'This parent would create a location hierarchy cycle.')
                    break
                visited.add(parent.pk)
                parent = parent.parent_location
        return cleaned
