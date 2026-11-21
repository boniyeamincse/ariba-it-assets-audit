from .models import SystemSettings


DEFAULTS = {
    'application_name': 'IT Asset Audit & Inventory',
    'application_short_name': 'IT Audit',
    'organization_name': 'Akij Group',
    'default_dashboard': 'overview',
    'default_landing_page': 'dashboard',
    'country': 'Bangladesh',
    'financial_year_start': 7,
    'primary_color': '#2563eb',
    'secondary_color': '#0f172a',
    'default_theme': 'light',
    'dashboard_layout': 'comfortable',
    'asset_status_labels': 'Working / In-Use\nBackup / Spare\nFaulty / Under Repair\nDamaged / Scrap',
    'asset_conditions': 'New\nGood\nFair\nDamaged',
    'asset_criticalities': 'Critical\nHigh\nMedium\nLow',
    'ownership_types': 'Owned\nLeased\nRented',
    'procurement_types': 'Purchased\nDonated',
    'asset_currency': 'BDT',
    'default_warranty_months': 0,
    'asset_id_prefix': '',
    'asset_id_include_company': True,
    'asset_id_include_category': True,
    'asset_id_include_location': False,
    'asset_id_company_code': '',
    'asset_id_location_code': '',
    'asset_id_category_code': '',
    'asset_id_start': 10001,
    'asset_id_length': 5,
    'asset_id_separator': '-',
    'notification_frequency': 'immediate',
    'minimum_password_length': 8,
    'max_login_attempts': 0,
    'lockout_minutes': 15,
    'password_expiry_days': 0,
    'inactive_account_days': 0,
    'log_login_events': True,
    'audit_log_retention_days': 0,
    'backup_frequency': 'daily',
    'backup_time': '02:00',
    'backup_retention_days': 30,
    'backup_database': True,
    'language': 'en',
    'secondary_language': 'bn',
    'timezone': 'Asia/Dhaka',
    'date_format': 'd-m-Y',
    'time_format': 'H:i',
    'currency': 'BDT',
    'number_format': 'indian',
    # Email / SMTP Configuration
    'smtp_host': 'smtp.akij.net',
    'smtp_port': 587,
    'smtp_username': 'it-audit@akij.net',
    'smtp_password': '',
    'smtp_use_tls': True,
    'smtp_use_ssl': False,
    'smtp_from_email': 'it-audit@akij.net',
    'smtp_from_name': 'Akij Group IT Asset Audit',
    # Security Policies
    'force_password_change_on_first_login': False,
    # User & Access Policies
    'allow_self_registration': False,
    'default_user_role': 'PENDING',
    # Integration Settings
    'enable_api': True,
    'api_token_auth': True,
    'erp_sync_enabled': False,
    'erp_endpoint_url': '',
    'erp_auth_token': '',
    'ldap_auth_enabled': False,
    'ldap_server_uri': '',
    'ldap_base_dn': '',
    # Audit Log Settings
    'log_asset_changes': True,
    'log_export_events': True,
    'log_user_changes': True,
    # System Maintenance
    'maintenance_mode': False,
    'maintenance_message': 'Akij Group IT Asset Audit & Inventory System is currently undergoing scheduled maintenance. Please check back shortly.',
    'allow_admin_bypass': True,
    'database_auto_vacuum': True,
    'debug_logging': False,
}


def preferences(config=None):
    config = config if config is not None else SystemSettings.current()
    return {
        **DEFAULTS,
        **config.options,
        'support_email': config.support_email,
        'session_minutes': config.session_minutes,
        'user_page_size': config.user_page_size,
        'activity_page_size': config.activity_page_size,
    }


def request_preferences(request):
    if not hasattr(request, 'system_preferences'):
        request.system_preferences = preferences()
    return request.system_preferences
