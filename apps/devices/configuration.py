from calendar import monthrange
import re


ASSET_METADATA = {
    'condition': ('Condition', 'asset_conditions'),
    'criticality': ('Criticality', 'asset_criticalities'),
    'ownership_type': ('Ownership', 'ownership_types'),
    'procurement_type': ('Procurement', 'procurement_types'),
}


def asset_tag_components(config, location, category):
    specific_codes = (
        ('company', location.company.short_code),
        ('location', location.code),
        ('category', category.code),
    )
    codes = [config.get(f'asset_id_{key}_code') or (re.sub(r'[^A-Z0-9]', '', actual.upper())[:8] or key.upper())
             for key, actual in specific_codes]
    return [config['asset_id_prefix'], *codes]


def add_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def asset_status_choices(config):
    from apps.devices.models import Asset

    labels = config['asset_status_labels'].splitlines()
    return [(key, labels[index]) for index, (key, _) in enumerate(Asset.STATUS_CHOICES)]
