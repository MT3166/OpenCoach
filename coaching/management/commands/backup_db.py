import sqlite3
from contextlib import closing
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = '创建一致的 SQLite 备份'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, **options):
        source = Path(settings.DATABASES['default']['NAME']).resolve()
        target = Path(options['output']).resolve()
        if not source.exists() or target.exists() or source == target:
            raise CommandError('源数据库须存在，备份目标须为新文件')
        target.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=20)) as database:
            with closing(sqlite3.connect(target)) as backup:
                database.backup(backup)
        self.stdout.write(str(target))
