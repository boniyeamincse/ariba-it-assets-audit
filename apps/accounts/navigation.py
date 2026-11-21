from django.urls import reverse

from apps.accounts.access import CENTRAL_ROLES, DASHBOARD_ROUTES, Role


_GROUPS = (
    ('Workspace', (
        ('Dashboard', 'dashboard', 'fa-gauge-high', ('home', *DASHBOARD_ROUTES.values()), None),
    )),
    ('Inventory', (
        ('Locations', 'location_list', 'fa-building', ('location_create', 'location_edit'), None),
        ('Asset Inventory', 'asset_list', 'fa-boxes-stacked', ('asset_create', 'asset_edit', 'asset_detail', 'asset_delete', 'asset_retire'), None),
        ('Software & Licenses', 'software_list', 'fa-key', (), None),
        ('Domains & SSL', 'domain_list', 'fa-globe', ('domain_create', 'domain_edit', 'domain_detail', 'domain_delete'), None),
        ('Device Catalog', 'category_list', 'fa-layer-group', (), 'central'),
        ('Import Assets', 'asset_import_csv', 'fa-file-csv', ('asset_sample_csv',), 'central'),
    )),
    ('Audits & Reports', (
        ('Audit Records', 'audit_list', 'fa-clipboard-list', (
            'audit_create', 'audit_edit', 'audit_detail', 'audit_print',
        ), None),
        ('Location Matrix', 'matrix', 'fa-table-cells', ('export_excel_matrix',), None),
    )),
    ('Administration', (
        ('User Management', 'administration_users', 'fa-users', ('administration_user_create', 'administration_user_edit'), 'central'),
        ('Roles & Permissions', 'administration_roles', 'fa-user-shield', ('administration_role_create',), 'central'),
        ('Activity Logs', 'activity_logs', 'fa-list-check', ('legacy_activity_logs',), 'central'),
        ('System Settings', 'administration_settings', 'fa-gear', ('administration_settings_section',), 'central'),
        ('Django Admin', 'admin:index', 'fa-screwdriver-wrench', (), 'super'),
    )),
)

_SUBPAGE_LABELS = {
    'location_create': 'New location',
    'location_edit': 'Edit location',
    'asset_create': 'New asset',
    'asset_edit': 'Edit asset',
    'asset_detail': 'Asset details',
    'asset_delete': 'Retire asset',
    'asset_retire': 'Retire asset',
    'domain_create': 'Register domain',
    'domain_edit': 'Edit domain',
    'domain_detail': 'Domain details',
    'domain_delete': 'Delete domain',
    'audit_create': 'New audit',
    'audit_edit': 'Edit audit',
    'audit_detail': 'Audit details',
    'administration_user_create': 'New user',
    'administration_user_edit': 'Edit user',
    'administration_role_create': 'Add role',
}

_CREATE_ACTIONS = (
    ('New Asset', 'asset_create', 'fa-box', None),
    ('New Domain', 'domain_create', 'fa-globe', 'central'),
    ('New Audit', 'audit_create', 'fa-clipboard-check', None),
    ('New Location', 'location_create', 'fa-building', 'central'),
    ('Add Role', 'administration_role_create', 'fa-user-shield', 'super'),
)


def portal_navigation(request, role):
    if role not in DASHBOARD_ROUTES:
        return {'nav_sections': (), 'nav_current': None, 'nav_actions': ()}

    allowed = {None}
    if role in CENTRAL_ROLES:
        allowed.add('central')
    if role == Role.SUPER_ADMIN:
        allowed.add('super')

    match = request.resolver_match
    current = match.url_name if match else None
    sections = []
    active_entry = None
    for group, entries in _GROUPS:
        links = []
        for label, route, icon, related, permission in entries:
            if permission not in allowed:
                continue
            entry = {
                'label': label,
                'url': reverse(route),
                'icon': icon,
            }
            if current == route or current in related:
                subpage = _SUBPAGE_LABELS.get(current)
                entry['current'] = 'location' if subpage else 'page'
                active_entry = {**entry, 'group': group, 'subpage': subpage}
            links.append(entry)
        if links:
            sections.append({'label': group, 'links': links})

    return {
        'nav_sections': sections,
        'nav_current': active_entry,
        'nav_actions': [
            {'label': label, 'url': reverse(route), 'icon': icon}
            for label, route, icon, permission in _CREATE_ACTIONS if permission in allowed
        ],
    }
