import os
import shutil
import sqlite3
import tarfile
from datetime import date, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils import timezone

from apps.common.models import SystemSettings
from apps.common.preferences import preferences


def write_status(status, successful_at=None):
    with transaction.atomic():
        config, _ = SystemSettings.objects.select_for_update().get_or_create(pk=1)
        config.options['last_backup_status'] = status
        if successful_at:
            config.options['last_backup_at'] = successful_at
        config.save(update_fields=['options'])


def create_database_backup(destination):
    database = connections['default'].settings_dict
    if database['ENGINE'] != 'django.db.backends.sqlite3':
        raise CommandError('The configured database requires a database-specific backup runner.')
    origin = Path(database['NAME']).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(origin, uri=True) as source, sqlite3.connect(destination) as target:
        source.backup(target)
        if target.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise CommandError('Database backup verification failed.')


def create_media_backup(destination):
    media = Path(settings.MEDIA_ROOT)
    with tarfile.open(destination, 'w:gz') as archive:
        if media.is_dir():
            archive.add(media, arcname='media', filter=lambda entry: entry if entry.isfile() or entry.isdir() else None)


class Command(BaseCommand):
    help = 'Run the configured, due SQLite and media backup. Call this periodically from the host scheduler.'

    def add_arguments(self, parser):
        parser.add_argument('--now', action='store_true', help='Run today without waiting for the configured weekday or time.')

    def handle(self, *args, **options):
        config = preferences()
        if not config.get('automatic_backups'):
            self.stdout.write('Automatic backups are disabled.')
            return
        now = timezone.localtime(timezone=ZoneInfo(config['timezone']))
        if not options['now'] and (now.time() < time.fromisoformat(config['backup_time']) or (
            config['backup_frequency'] == 'weekly' and now.weekday() != 0
        )):
            self.stdout.write('No backup is due.')
            return
        if not settings.SYSTEM_BACKUP_ROOT:
            raise CommandError('Configure AUDIT_BACKUP_ROOT outside the served directories.')
        root = Path(settings.SYSTEM_BACKUP_ROOT).resolve()
        storage = (root / (config.get('backup_storage_location') or '')).resolve()
        protected = [Path(settings.MEDIA_ROOT).resolve(), Path(settings.STATIC_ROOT).resolve(), settings.BASE_DIR.resolve()]
        if not storage.is_relative_to(root) or any(storage.is_relative_to(path) for path in protected):
            raise CommandError('Backup storage must stay under AUDIT_BACKUP_ROOT and outside the application directory.')
        if not (config.get('backup_database') or config.get('backup_media')):
            raise CommandError('Select database or media backups first.')

        storage.mkdir(mode=0o700, parents=True, exist_ok=True)
        final = storage / f'audit-backup-{now.date().isoformat()}'
        if final.exists():
            self.stdout.write('Today’s backup already exists.')
            return

        try:
            with TemporaryDirectory(prefix='.audit-working-', dir=storage) as temp_dir:
                staging = Path(temp_dir)
                if config.get('backup_database'):
                    create_database_backup(staging / 'database.sqlite3')
                if config.get('backup_media'):
                    create_media_backup(staging / 'media.tar.gz')
                (staging / '.audit-backup').touch()
                os.rename(staging, final)
            write_status('Successful', now.isoformat())
        except (OSError, sqlite3.Error, CommandError) as error:
            if final.is_dir():
                self.stdout.write('Today’s backup already exists.')
                return
            write_status('Failed. Check the backup command output.')
            raise CommandError(str(error)) from error

        cutoff = now.date() - timedelta(days=config['backup_retention_days'])
        for backup in storage.glob('audit-backup-*'):
            try:
                backup_date = date.fromisoformat(backup.name.removeprefix('audit-backup-'))
            except ValueError:
                continue
            if backup_date < cutoff and not backup.is_symlink() and backup.is_dir() and (backup / '.audit-backup').is_file():
                shutil.rmtree(backup)
        self.stdout.write(self.style.SUCCESS('Backup completed.'))
