from calendar import monthrange
import re


ASSET_METADATA = {
    'condition': ('Condition', 'asset_conditions'),
    'criticality': ('Criticality', 'asset_criticalities'),
    'ownership_type': ('Ownership', 'ownership_types'),
    'procurement_type': ('Procurement', 'procurement_types'),
}


# Standardized Device Category Codes for Enterprise Asset Tagging (COMPANY-CATEGORY-SERIAL)
DEVICE_TYPE_CATEGORY_CODES = {
    'router': 'ROU',
    'switch': 'SWT',
    'firewall': 'FWL',
    'access point': 'AP',
    'ap': 'AP',
    'unifi': 'AP',
    'wifi': 'AP',
    'server': 'SRV',
    'database server': 'SRV',
    'db server': 'SRV',
    'web server': 'SRV',
    'app server': 'SRV',
    'file server': 'SRV',
    'desktop': 'DSK',
    'pc': 'DSK',
    'workstation': 'DSK',
    'laptop': 'LAP',
    'notebook': 'LAP',
    'printer': 'PRT',
    'scanner': 'SCN',
    'storage': 'STR',
    'san': 'STR',
    'cctv': 'CCTV',
    'camera': 'CCTV',
    'nvr': 'CCTV',
    'dvr': 'CCTV',
    'ups': 'UPS',
    'ips': 'UPS',
    'monitor': 'MON',
    'display': 'MON',
    'screen': 'MON',
    'ip phone': 'IPP',
    'phone': 'IPP',
    'telephone': 'IPP',
    'nas': 'NAS',
    'virtual machine': 'VM',
    'virtual server': 'VM',
    'cloud vm': 'VM',
    'vm': 'VM',
    'software': 'LIC',
    'license': 'LIC',
    'erp': 'ERP',
    'cloud': 'CLD',
    'database': 'DB',
    'certificate': 'SSL',
    'ssl': 'SSL',
    'domain': 'DOM',
    'rack': 'RCK',
}


def resolve_category_code(device_type=None, category=None):
    """
    Resolves standard 2-4 letter category code for asset tag (e.g. ROU, SWT, LAP, SRV).
    Uses whole-word boundary matching sorted by keyword length to prevent substring clashes.
    """
    if device_type and hasattr(device_type, 'name'):
        name_lower = device_type.name.lower()
        # Sort keywords by length descending so e.g. 'laptop' matches before 'ap'
        for keyword in sorted(DEVICE_TYPE_CATEGORY_CODES.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(keyword) + r'\b', name_lower):
                return DEVICE_TYPE_CATEGORY_CODES[keyword]
        cleaned = re.sub(r'[^A-Z0-9]', '', device_type.name.upper())
        if len(cleaned) >= 3:
            return cleaned[:4]
            
    if category and hasattr(category, 'code'):
        cat_cleaned = re.sub(r'[^A-Z0-9]', '', category.code.upper())
        return cat_cleaned[:4] or 'AST'
        
    return 'AST'


def asset_tag_components(config, location, category, device_type=None):
    """
    Builds the constituent tokens for an asset tag adhering to the standard:
    COMPANY - CATEGORY - SERIAL (e.g. APL-ROU-10001)
    Supports optional prefix (e.g. AST) and optional location code.
    """
    parts = []

    # 1. Prefix (Optional - e.g. AST, IT, or empty)
    prefix = (config.get('asset_id_prefix') or '').strip().upper()
    if prefix:
        parts.append(prefix)

    # 2. Company Code (Default Enabled - e.g. APL, AMFL, AJML, ACC)
    include_company = config.get('asset_id_include_company', True)
    if include_company:
        comp_override = (config.get('asset_id_company_code') or '').strip().upper()
        if comp_override:
            parts.append(comp_override)
        elif location and hasattr(location, 'company') and location.company and location.company.short_code:
            parts.append(location.company.short_code.upper())
        else:
            parts.append('APL')

    # 3. Location Code (Optional - Default False per recommendation, unless explicitly provided)
    include_location = config.get('asset_id_include_location', False)
    loc_override = (config.get('asset_id_location_code') or '').strip().upper()
    if loc_override:
        parts.append(loc_override)
    elif include_location and location and hasattr(location, 'code') and location.code:
        parts.append(re.sub(r'[^A-Z0-9]', '', location.code.upper())[:8])

    # 4. Device Category Code (Default Enabled - e.g. ROU, SWT, LAP, DSK, SRV)
    include_category = config.get('asset_id_include_category', True)
    if include_category:
        cat_override = (config.get('asset_id_category_code') or '').strip().upper()
        if cat_override:
            parts.append(cat_override)
        else:
            parts.append(resolve_category_code(device_type, category))

    return [p for p in parts if p]


def add_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def asset_status_choices(config):
    from apps.devices.models import Asset

    labels = config['asset_status_labels'].splitlines()
    return [(key, labels[index]) for index, (key, _) in enumerate(Asset.STATUS_CHOICES)]
