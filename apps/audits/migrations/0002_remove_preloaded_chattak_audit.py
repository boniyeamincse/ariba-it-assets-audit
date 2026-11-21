from datetime import date

from django.db import migrations


LEGACY_AUDIT_REMARKS = 'Comprehensive physical IT asset verification completed at Chattak Factory.'


def remove_preloaded_audit(apps, schema_editor):
    AuditSession = apps.get_model('audits', 'AuditSession')
    database = schema_editor.connection.alias
    AuditSession.objects.using(database).filter(
        location__code='APL-CHATTAK',
        audit_date=date(2026, 11, 21),
        remarks=LEGACY_AUDIT_REMARKS,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('audits', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(remove_preloaded_audit, migrations.RunPython.noop),
    ]
