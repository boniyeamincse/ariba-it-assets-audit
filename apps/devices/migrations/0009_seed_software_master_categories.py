from django.db import migrations

SOFTWARE_CATEGORIES_39 = [
    'Operating System',
    'Office & Productivity',
    'Web Browser',
    'Graphics & Design',
    'Video & Audio Editing',
    'CAD & Engineering',
    'Accounting & Finance',
    'ERP & Business Applications',
    'HR & Payroll',
    'Database Management',
    'Database Administration',
    'Programming & Development',
    'Version Control',
    'Network Management',
    'Cybersecurity & Endpoint Protection',
    'SIEM & Log Management',
    'Vulnerability Management',
    'Firewall & VPN Client',
    'Remote Access & Support',
    'Virtualization',
    'Container & Orchestration',
    'Web & Application Server',
    'Backup & Recovery',
    'Monitoring & Observability',
    'Cloud & Storage',
    'Email & Communication',
    'Collaboration & Project Management',
    'PDF & Document Management',
    'File Compression & Archiving',
    'Media Player',
    'Printer & Scanner Software',
    'Device Drivers & Firmware Utilities',
    'Mobile Device Management',
    'Industrial & Factory Software',
    'CCTV & Surveillance Software',
    'Utility & System Tools',
    'Education & Training',
    'Business-specific Software',
    'Other Software',
]


def seed_software_categories(apps, schema_editor):
    DeviceCategory = apps.get_model('devices', 'DeviceCategory')
    DeviceType = apps.get_model('devices', 'DeviceType')

    cat, _ = DeviceCategory.objects.get_or_create(
        code='LOGICAL',
        defaults={'name': 'Software & Logical Assets', 'order': 3}
    )

    for order, name in enumerate(SOFTWARE_CATEGORIES_39, 1):
        DeviceType.objects.get_or_create(
            category=cat,
            name=name,
            defaults={
                'order': order,
                'tag_category_code': 'LIC' if name not in ('ERP & Business Applications', 'Virtualization', 'Container & Orchestration', 'Database Management', 'Cloud & Storage') else ('ERP' if 'ERP' in name else ('VM' if 'Virtual' in name or 'Container' in name else 'CLD')),
            }
        )


def unseed_software_categories(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0008_asset_compliance_status_asset_remediation_plan_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_software_categories, unseed_software_categories),
    ]
