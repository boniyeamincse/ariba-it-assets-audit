from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from apps.accounts.access import LOCAL_TYPES, Role
from apps.accounts.models import RoleDefinition, UserProfile
from apps.locations.models import Location


def managed_role_options(actor_role):
    roles = [Role.FACTORY_ADMIN, Role.DEPOT_ADMIN, Role.PENDING]
    if actor_role == Role.SUPER_ADMIN:
        roles.insert(0, Role.HO_ADMIN)
    options = {role.value: (role, None, role.label) for role in roles}
    custom_roles = RoleDefinition.objects.filter(is_active=True, base_role__in=roles)
    options.update({f'custom:{custom.pk}': (custom.base_role, custom, custom.name) for custom in custom_roles})
    return options


class RoleDefinitionForm(forms.ModelForm):
    class Meta:
        model = RoleDefinition
        fields = ['name', 'base_role', 'description']
        labels = {'name': 'Role name', 'base_role': 'Base role'}
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'base_role': 'The new role uses the permissions and location scope of this base role.'}

    def clean_name(self):
        name = self.cleaned_data['name']
        reserved = {value.casefold() for value, label in Role.choices} | {label.casefold() for value, label in Role.choices}
        if name.casefold() in reserved or RoleDefinition.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('This role name is already in use.')
        return name


class UserFilterForm(forms.Form):
    q = forms.CharField(label='Search', required=False, max_length=150,
                        widget=forms.TextInput(attrs={'placeholder': 'Name, username or email'}))
    role = forms.ChoiceField(required=False)
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses'), ('active', 'Active'), ('inactive', 'Inactive')])
    location = forms.ModelChoiceField(queryset=Location.objects.none(), empty_label='All locations', required=False)

    def __init__(self, *args, actor_role, **kwargs):
        super().__init__(*args, **kwargs)
        self.role_options = managed_role_options(actor_role)
        self.fields['role'].choices = [('', 'All roles'), *((key, option[2]) for key, option in self.role_options.items())]
        self.fields['location'].queryset = Location.objects.order_by('name', 'code')


class ManagedUserForm(forms.ModelForm):
    phone_number = forms.CharField(label='Work phone', max_length=30, required=False,
                                   widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}))
    designation = forms.CharField(label='Job title', max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'autocomplete': 'organization-title'}))
    role = forms.ChoiceField()
    assigned_locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select locations that match the selected local role.',
    )
    password = forms.CharField(
        required=False, strip=False, label='New password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {'email': 'Work email', 'is_active': 'Account active'}

    @property
    def sections(self):
        return (
            ('Account details', (self['username'], self['first_name'], self['last_name'], self['email'])),
            ('Work information', (self['designation'], self['phone_number'])),
            ('Role and location access', (self['role'], self['is_active'], self['assigned_locations'])),
            ('Password', (self['password'],)),
        )

    def __init__(self, *args, actor_role, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = getattr(self.instance, 'profile', None)
        self.role_options = managed_role_options(actor_role)
        self.fields['role'].choices = [(key, option[2]) for key, option in self.role_options.items()]
        self.fields['is_active'].help_text = 'Inactive accounts cannot sign in.'
        locations = Location.objects.filter(location_type__in=LOCAL_TYPES.values())
        self.fields['assigned_locations'].queryset = locations.order_by('company__name', 'name')
        self.fields['password'].required = self.instance._state.adding
        if self.profile:
            self.initial['role'] = f'custom:{self.profile.custom_role_id}' if self.profile.custom_role_id else self.profile.role
            self.initial['phone_number'] = self.profile.phone_number
            self.initial['designation'] = self.profile.designation
            self.initial['assigned_locations'] = self.profile.assigned_locations.filter(pk__in=locations)
            self.fields['password'].help_text = 'Leave blank to keep the current password.'

    def clean(self):
        cleaned = super().clean()
        option = self.role_options.get(cleaned.get('role'))
        role = option[0] if option else None
        locations = cleaned.get('assigned_locations')
        if role and role != Role.PENDING and locations is not None:
            allowed_type = LOCAL_TYPES.get(role)
            if locations.exclude(location_type=allowed_type).exists():
                self.add_error('assigned_locations', 'Assignments must match the selected role. Clear assignments for HO Admin.')
        return cleaned

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password', error)

    def save_account(self):
        user = self.save(commit=False)
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role, profile.custom_role, _ = self.role_options[self.cleaned_data['role']]
        if 'phone_number' in self.data:
            profile.phone_number = self.cleaned_data['phone_number'] or None
        if 'designation' in self.data:
            profile.designation = self.cleaned_data['designation'] or UserProfile._meta.get_field('designation').get_default()
        profile.save(update_fields=['role', 'custom_role', 'phone_number', 'designation', 'updated_at'])
        profile.assigned_locations.set(self.cleaned_data['assigned_locations'])
        return user
