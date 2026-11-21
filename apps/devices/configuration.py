from calendar import monthrange
import re


ASSET_METADATA = {
    'condition': ('Condition', 'asset_conditions'),
    'criticality': ('Criticality', 'asset_criticalities'),
    'ownership_type': ('Ownership', 'ownership_types'),
    'procurement_type': ('Procurement', 'procurement_types'),
}


TAG_CATEGORY_CHOICES = (
    ('ROU', 'Router'), ('SWT', 'Switch'), ('FWL', 'Firewall'),
    ('AP', 'Access point'), ('SRV', 'Server'), ('DSK', 'Desktop'),
    ('LAP', 'Laptop'), ('PRT', 'Printer / scanner'), ('STR', 'Storage'),
    ('CCTV', 'CCTV / NVR'), ('UPS', 'UPS / IPS'), ('MON', 'Monitor'),
    ('IPP', 'IP phone'), ('NAS', 'NAS'), ('VM', 'Virtual machine'),
    ('LIC', 'Software licence'), ('ERP', 'ERP licence'), ('SSL', 'TLS certificate'),
    ('CLD', 'Cloud / database'), ('RCK', 'Rack'), ('OTHR', 'Other (review classification)'),
)


# These keywords only suggest a code when a catalogue record is first created.
_TAG_CATEGORY_KEYWORDS = (
    ('ERP', r'erp|sap'),
    ('SSL', r'ssl|tls|certificate'),
    ('NAS', r'nas|network attached storage'),
    ('VM', r'virtual machine|virtual server|cloud vm|vm'),
    ('CCTV', r'cctv|camera|nvr|dvr'),
    ('AP', r'access point|unifi|wifi|wi-fi|ap'),
    ('PRT', r'printer|scanner'),
    ('FWL', r'firewall'),
    ('ROU', r'router'),
    ('SWT', r'switch'),
    ('CLD', r'cloud|database'),
    ('SRV', r'server'),
    ('DSK', r'desktop|workstation|pc'),
    ('LAP', r'laptop|notebook|macbook'),
    ('STR', r'storage|san|das'),
    ('UPS', r'ups|ips'),
    ('MON', r'monitor|display|screen'),
    ('IPP', r'ip phone|phone|telephone|voip'),
    ('LIC', r'software|license|licence|chat|slack|teams|messaging|communication'),
    ('RCK', r'rack|cabinet'),
)


def suggest_tag_category(name):
    for code, keywords in _TAG_CATEGORY_KEYWORDS:
        if re.search(rf'\b(?:{keywords})\b', name, re.IGNORECASE):
            return code
    return 'OTHR'


def format_asset_tag(config, number, *, company_code, location_code, tag_category_code):
    tokens = [config['asset_id_prefix']]
    if config['asset_id_include_company']:
        tokens.append(config['asset_id_company_code'] or re.sub(r'[^A-Z0-9]', '', company_code.upper()))
    if config['asset_id_include_location']:
        tokens.append(config['asset_id_location_code'] or re.sub(r'[^A-Z0-9]', '', location_code.upper())[:8])
    if config['asset_id_include_category']:
        tokens.append(config['asset_id_category_code'] or tag_category_code)
    tokens.append(str(number).zfill(config['asset_id_length']))
    return config['asset_id_separator'].join(token.upper() for token in tokens if token)


def example_asset_tag(config):
    return format_asset_tag(config, config['asset_id_start'], company_code='APL', location_code='HO', tag_category_code='ROU')


def normalize_asset_tag(tag):
    return tag.strip().upper()


def add_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def asset_status_choices(config):
    from apps.devices.models import Asset

    labels = config['asset_status_labels'].splitlines()
    return [(key, labels[index]) for index, (key, _) in enumerate(Asset.STATUS_CHOICES)]
