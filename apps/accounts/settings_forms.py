from copy import deepcopy
from datetime import time
from ipaddress import ip_network
from pathlib import PurePath
from urllib.parse import urlsplit
from zoneinfo import available_timezones

from django import forms
from django.core.validators import RegexValidator, validate_email

from apps.common.preferences import preferences
from apps.locations.models import Company


def text(label, maximum=150, required=False):
    return forms.CharField(label=label, max_length=maximum, required=required)


def area(label, maximum=1000):
    return forms.CharField(label=label, max_length=maximum, required=False, widget=forms.Textarea(attrs={'rows': 3}))


def dropdown(label, choices):
    return forms.ChoiceField(label=label, choices=choices)


def integer(label, minimum, maximum, required=True):
    return forms.IntegerField(label=label, min_value=minimum, max_value=maximum, required=required)


def switch(label):
    return forms.BooleanField(label=label, required=False)


def code(label, maximum=10, required=False):
    return forms.CharField(
        label=label, required=required, max_length=maximum,
        validators=[RegexValidator(r'^[A-Za-z0-9]+$', 'Use letters and digits only.')],
    )


def image_reference(value):
    if not value:
        return
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise forms.ValidationError('Enter a valid image URL or static/media path.') from exc
    hosted = parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
    local = not parsed.netloc and not parsed.scheme and parsed.path.startswith(('/static/', '/media/'))
    if not (hosted or local) or any(c.isspace() or c in '\\<>"' for c in value):
        raise forms.ValidationError('Use an HTTPS image URL or a /static/ or /media/ path.')


def logo(label):
    return forms.CharField(label=label, required=False, max_length=500, validators=[image_reference],
                           help_text='HTTPS image URL or an existing static/media path.')


def color(label):
    return forms.CharField(
        label=label, max_length=7, widget=forms.TextInput(attrs={'type': 'color'}),
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Use a six-digit hex colour.')],
    )


def currency(label):
    return forms.CharField(label=label, max_length=3, validators=[RegexValidator(r'^[A-Za-z]{3}$', 'Use a three-letter currency code.')])


CATEGORIES = {
    'general': 'General Settings',
    'organization': 'Organization Settings',
    'appearance': 'Appearance Settings',
    'assets': 'Asset Configuration',
    'asset-id': 'Asset ID Configuration',
    'notifications': 'Notification Settings',
    'email': 'Email Configuration',
    'security': 'Security Settings',
    'access': 'User & Access Settings',
    'backup': 'Backup Settings',
    'audit-log': 'Audit Log Settings',
    'localization': 'Localization Settings',
    'integration': 'Integration Settings',
    'maintenance': 'System Maintenance',
}

SECTION_METADATA = {
    'general': {
        'title': 'General Settings',
        'subtitle': 'Application configuration',
        'icon': 'fa-sliders',
    },
    'organization': {
        'title': 'Organization Settings',
        'subtitle': 'Group and company information',
        'icon': 'fa-building',
    },
    'appearance': {
        'title': 'Appearance Settings',
        'subtitle': 'Theme, logo and branding',
        'icon': 'fa-palette',
    },
    'assets': {
        'title': 'Asset Configuration',
        'subtitle': 'Categories, types and statuses',
        'icon': 'fa-boxes-stacked',
    },
    'asset-id': {
        'title': 'Asset ID Configuration',
        'subtitle': 'Automatic asset numbering',
        'icon': 'fa-barcode',
    },
    'notifications': {
        'title': 'Notification Settings',
        'subtitle': 'Email and alert preferences',
        'icon': 'fa-bell',
    },
    'email': {
        'title': 'Email Configuration',
        'subtitle': 'SMTP server settings',
        'icon': 'fa-envelope',
    },
    'security': {
        'title': 'Security Settings',
        'subtitle': 'Password and login policies',
        'icon': 'fa-shield-halved',
    },
    'access': {
        'title': 'User & Access Settings',
        'subtitle': 'Account and access policies',
        'icon': 'fa-user-lock',
    },
    'backup': {
        'title': 'Backup Settings',
        'subtitle': 'Backup and restore',
        'icon': 'fa-database',
    },
    'audit-log': {
        'title': 'Audit Log Settings',
        'subtitle': 'Activity logging and retention',
        'icon': 'fa-clock-rotate-left',
    },
    'localization': {
        'title': 'Localization Settings',
        'subtitle': 'Language, timezone and date format',
        'icon': 'fa-globe',
    },
    'integration': {
        'title': 'Integration Settings',
        'subtitle': 'API and external integrations',
        'icon': 'fa-plug',
    },
    'maintenance': {
        'title': 'System Maintenance',
        'subtitle': 'Maintenance mode and system health',
        'icon': 'fa-screwdriver-wrench',
    },
}

CORE_FIELDS = ('session_minutes', 'activity_page_size', 'user_page_size', 'support_email')

FIELDS = {
    'general': {
        'application_name': text('Application name', required=True),
        'application_short_name': text('Application short name', 30, True),
        'application_description': area('Application description'),
        'application_url': forms.URLField(label='Application URL', required=False, assume_scheme='https'),
        'organization_name': text('Organization name', required=True),
        'support_email': forms.EmailField(label='Support email', required=False),
        'support_phone': text('Support phone', 30),
        'default_dashboard': dropdown('Default dashboard', [('overview', 'Role dashboard'), ('matrix', 'Asset matrix')]),
        'default_landing_page': dropdown('Default landing page', [('dashboard', 'Dashboard preference'), ('assets', 'Assets'), ('audits', 'Audit records')]),
        'maintenance_mode': switch('Maintenance mode'),
    },
    'organization': {
        'group_name': text('Group name'), 'group_logo': logo('Group logo'), 'group_address': area('Group address'),
        'country': text('Country', 80), 'city': text('City', 80),
        'contact_email': forms.EmailField(label='Contact email', required=False),
        'contact_number': text('Contact number', 30),
        'website': forms.URLField(label='Website', required=False, assume_scheme='https'),
        'financial_year_start': forms.TypedChoiceField(label='Financial year start', coerce=int, choices=list(enumerate(
            ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), 1))),
        'default_company': forms.ModelChoiceField(label='Default company', queryset=Company.objects.none(), required=False),
        'company_code_prefix': code('Company code prefix'),
    },
    'appearance': {
        'application_logo': logo('Application logo'), 'login_logo': logo('Login page logo'),
        'favicon': logo('Favicon'), 'sidebar_logo': logo('Sidebar logo'),
        'primary_color': color('Primary colour'), 'secondary_color': color('Secondary colour'),
        'default_theme': dropdown('Default theme', [('light', 'Light'), ('dark', 'Dark'), ('system', 'System')]),
        'sidebar_collapsed': switch('Collapse sidebar by default'),
        'dashboard_layout': dropdown('Dashboard layout', [('comfortable', 'Comfortable'), ('compact', 'Compact')]),
    },
    'assets': {
        'asset_status_labels': area('Asset status labels'),
        'asset_conditions': area('Asset conditions'),
        'asset_criticalities': area('Asset criticality'),
        'ownership_types': area('Ownership types'),
        'procurement_types': area('Procurement types'),
        'asset_currency': currency('Default currency'),
        'default_warranty_months': integer('Default warranty period (months)', 0, 600),
    },
    'asset-id': {
        'asset_id_prefix': code('ID prefix', required=True),
        'asset_id_company_code': code('Company code override', 12),
        'asset_id_location_code': code('Location code override', 12),
        'asset_id_category_code': code('Category code override', 12),
        'asset_id_start': integer('Starting number', 1, 999999999),
        'asset_id_length': integer('Number length', 1, 9),
        'asset_id_separator': dropdown('Separator', [('-', 'Hyphen (-)'), ('_', 'Underscore (_)')]),
    },
    'notifications': {
        'email_notifications': switch('Enable email notifications'),
        'notify_asset_created': switch('New asset created'), 'notify_asset_assigned': switch('Asset assigned'),
        'notify_asset_transferred': switch('Asset transferred'), 'notify_warranty_expiry': switch('Warranty expiry alert'),
        'notify_license_expiry': switch('License expiry alert'), 'notify_maintenance_reminder': switch('Maintenance reminder'),
        'notify_unknown_device': switch('Unknown device detected'),
        'notification_recipients': area('Notification recipients'),
        'notification_frequency': dropdown('Notification frequency', [('immediate', 'On event'), ('daily', 'Daily digest'), ('weekly', 'Weekly digest')]),
    },
    'email': {
        'smtp_host': text('SMTP host / server', 255, required=False),
        'smtp_port': integer('SMTP port', 1, 65535, required=False),
        'smtp_username': text('SMTP username / account', 150, required=False),
        'smtp_password': forms.CharField(label='SMTP password / app key', widget=forms.PasswordInput(render_value=True), required=False),
        'smtp_use_tls': switch('Use TLS encryption (Port 587)'),
        'smtp_use_ssl': switch('Use SSL encryption (Port 465)'),
        'smtp_from_email': forms.EmailField(label='From email address', required=False),
        'smtp_from_name': text('From sender name', 100, required=False),
    },
    'security': {
        'minimum_password_length': integer('Minimum password length', 8, 128),
        'password_complexity': switch('Require uppercase, lowercase, number and symbol'),
        'password_expiry_days': integer('Password expiry (days; 0 disables)', 0, 3650),
        'max_login_attempts': integer('Maximum login attempts before lockout (0 disables)', 0, 50),
        'lockout_minutes': integer('Account lockout duration (minutes)', 1, 1440),
        'session_minutes': integer('Session timeout (minutes)', 15, 1440),
        'two_factor_authentication': switch('Two-factor authentication (2FA) enforcement'),
        'force_password_change_on_first_login': switch('Force password change on initial sign-in'),
        'allowed_ip_addresses': area('Restricted Admin IP addresses and CIDR networks'),
    },
    'access': {
        'minimum_password_length': integer('Minimum password length', 8, 128),
        'password_complexity': switch('Require uppercase, lowercase, number and symbol'),
        'password_expiry_days': integer('Password expiry (days; 0 disables)', 0, 3650),
        'max_login_attempts': integer('Maximum login attempts (0 disables)', 0, 50),
        'lockout_minutes': integer('Account lockout duration (minutes)', 1, 1440),
        'session_minutes': integer('Session timeout (minutes)', 15, 1440),
        'two_factor_authentication': switch('Two-factor authentication'),
        'allowed_ip_addresses': area('Allowed IP addresses and networks'),
        'log_login_events': switch('Record login history'),
        'inactive_account_days': integer('Inactive account policy (days; 0 disables)', 0, 3650),
        'allow_self_registration': switch('Allow user self-registration'),
        'default_user_role': dropdown('Default role for new accounts', [('PENDING', 'Pending Approval'), ('AUDITOR', 'Auditor'), ('VIEWER', 'Viewer')]),
    },
    'backup': {
        'automatic_backups': switch('Enable automatic backups'),
        'backup_frequency': dropdown('Backup frequency', [('daily', 'Daily'), ('weekly', 'Weekly')]),
        'backup_time': forms.TimeField(label='Backup time', widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time'})),
        'backup_retention_days': integer('Backup retention (days)', 1, 3650),
        'backup_storage_location': text('Backup storage location', 255),
        'backup_database': switch('Database backup'),
        'backup_media': switch('Media/file backup'),
    },
    'audit-log': {
        'activity_page_size': integer('Activity logs per page', 10, 100),
        'user_page_size': integer('Users per page', 10, 100),
        'audit_log_retention_days': integer('Activity log retention (days; 0 keeps all)', 0, 3650),
        'log_asset_changes': switch('Record asset creation, modification and deletion events'),
        'log_export_events': switch('Record audit report and Excel/CSV download events'),
        'log_user_changes': switch('Record user creation and permission modification events'),
    },
    'localization': {
        'language': dropdown('Language', [('en', 'English'), ('bn', 'Bangla')]),
        'secondary_language': dropdown('Secondary language', [('bn', 'Bangla'), ('en', 'English')]),
        'timezone': dropdown('Timezone', [(zone, zone) for zone in sorted(available_timezones())]),
        'date_format': dropdown('Date format', [('d-m-Y', 'DD-MM-YYYY'), ('Y-m-d', 'YYYY-MM-DD'), ('d/m/Y', 'DD/MM/YYYY')]),
        'time_format': dropdown('Time format', [('H:i', '24 hour'), ('g:i A', '12 hour')]),
        'currency': currency('Currency'),
        'number_format': dropdown('Number format', [('indian', '1,00,000'), ('western', '100,000'), ('plain', '100000')]),
    },
    'integration': {
        'enable_api': switch('Enable REST API access'),
        'api_token_auth': switch('Require Bearer API token authentication'),
        'erp_sync_enabled': switch('Enable Akij Enterprise ERP synchronization'),
        'erp_endpoint_url': forms.URLField(label='ERP API endpoint URL', required=False, assume_scheme='https'),
        'erp_auth_token': text('ERP API authorization token / secret key', 255, required=False),
        'ldap_auth_enabled': switch('Enable Central LDAP / Active Directory authentication'),
        'ldap_server_uri': text('LDAP server URI (e.g. ldap://ad.akij.net:389)', 255, required=False),
        'ldap_base_dn': text('LDAP base DN (e.g. dc=akij,dc=net)', 255, required=False),
    },
    'maintenance': {
        'maintenance_mode': switch('Maintenance mode enabled'),
        'maintenance_message': area('Maintenance notice message displayed to users'),
        'allow_admin_bypass': switch('Allow Super Admin and Central Admin bypass during maintenance'),
        'database_auto_vacuum': switch('Automatic database vacuum & index optimization'),
        'debug_logging': switch('Verbose diagnostic logging for troubleshooting'),
    },
}

RESERVED = {
    'notify_license_expiry': 'Requires a licence inventory.',
    'notify_maintenance_reminder': 'Requires maintenance schedules.',
    'notify_unknown_device': 'Requires a device discovery service.',
    'password_expiry_days': 'Requires a password change and recovery workflow.',
    'two_factor_authentication': 'Requires enrolment, recovery and challenge screens.',
    'inactive_account_days': 'Requires an account review and reactivation policy.',
}


class SectionSettingsForm(forms.Form):
    def __init__(self, *args, section, config, editable, **kwargs):
        initial = preferences(config)
        if section == 'backup':
            initial['backup_time'] = time.fromisoformat(initial['backup_time'])
        super().__init__(*args, initial=initial, **kwargs)
        self.section = section
        self.fields = deepcopy(FIELDS[section])
        if section == 'organization':
            self.fields['default_company'].queryset = Company.objects.filter(is_active=True).order_by('name')
        for key, field in self.fields.items():
            field.disabled = not editable or key in RESERVED
            if key in RESERVED:
                field.help_text = RESERVED[key]
        for field in ('asset_status_labels', 'asset_conditions', 'asset_criticalities', 'ownership_types', 'procurement_types'):
            if field in self.fields:
                self.fields[field].help_text = 'One value per line. Status labels map to In Use, Backup, Repair and Scrap in that order.'

    def clean(self):
        result = super().clean()
        for name in ('asset_currency', 'currency', 'company_code_prefix', 'asset_id_prefix', 'asset_id_company_code', 'asset_id_location_code', 'asset_id_category_code'):
            if name in result:
                result[name] = result[name].upper()
        for name in ('asset_conditions', 'asset_criticalities', 'ownership_types', 'procurement_types', 'asset_status_labels'):
            if name in result:
                rows = [row.strip() for row in result[name].splitlines() if row.strip()]
                if not rows or len(rows) > 30 or any(len(row) > 60 for row in rows) or len(set(rows)) != len(rows):
                    self.add_error(name, 'Enter 1–30 unique values, each at most 60 characters.')
                elif name == 'asset_status_labels' and len(rows) != 4:
                    self.add_error(name, 'Enter four labels, one for each existing status.')
                else:
                    result[name] = '\n'.join(rows)
        if self.section == 'asset-id' and result.get('asset_id_start') and result.get('asset_id_length'):
            budget = len(result.get('asset_id_prefix', '')) + 4 + 12 + sum(
                len(result.get(f'asset_id_{part}_code') or '12345678') for part in ('company', 'location', 'category')
            )
            if budget > 50:
                self.add_error('asset_id_prefix', 'Shorten the prefix or code overrides to keep generated IDs within 50 characters.')
            if result['asset_id_start'] >= 10 ** result['asset_id_length']:
                self.add_error('asset_id_start', 'The starting number must fit in the selected length.')
        if self.section == 'notifications':
            recipients = [address.strip() for address in result.get('notification_recipients', '').replace(',', '\n').splitlines() if address.strip()]
            try:
                for address in recipients:
                    validate_email(address)
            except forms.ValidationError as exc:
                self.add_error('notification_recipients', exc)
            else:
                result['notification_recipients'] = '\n'.join(dict.fromkeys(recipients))
            if result.get('email_notifications') and not recipients:
                self.add_error('notification_recipients', 'Enter at least one recipient when email notifications are enabled.')
        if result.get('allowed_ip_addresses'):
            try:
                result['allowed_ip_addresses'] = '\n'.join(
                    str(ip_network(value.strip(), strict=False))
                    for value in result['allowed_ip_addresses'].replace(',', '\n').splitlines() if value.strip()
                )
            except ValueError:
                self.add_error('allowed_ip_addresses', 'Enter IP addresses or CIDR networks, one per line.')
        storage = result.get('backup_storage_location')
        if storage and (PurePath(storage).is_absolute() or '..' in PurePath(storage).parts):
            self.add_error('backup_storage_location', 'Use a relative folder within the configured backup root.')
        if result.get('automatic_backups') and not (result.get('backup_database') or result.get('backup_media')):
            self.add_error('automatic_backups', 'Select a database or media backup.')
        for key in ('default_company', 'backup_time'):
            if key in result:
                value = result[key]
                result[key] = (value.pk if key == 'default_company' else value.strftime('%H:%M')) if value else None
        return result
