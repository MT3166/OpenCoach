"""测试部署的 Linux 测试、备份恢复与重启持久化验收。"""
import base64
import getpass
import hashlib
import json
import paramiko
from remote import HOST, USERNAME, TARGET, FINGERPRINT, PinnedHostKey, run

SNAPSHOT_CODE = '''
import os, json, base64, io, sqlite3, tempfile, hashlib
from pathlib import Path
from contextlib import closing
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opencoach.settings')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from coaching.models import Student, Booking, CreditEntry, TrainingRecord, TrainingPlan, Submission, Kind, DirectLesson
from coaching.booking import balances
def snapshot():
    from django.contrib.auth import get_user_model
    models = [Student, Booking, CreditEntry, TrainingRecord, TrainingPlan, Submission, DirectLesson]
    records = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
    records['accounts'] = list(get_user_model().objects.order_by('pk').values('id','username','password','is_active','is_staff'))
    digest = hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    return {'counts': {model.__name__: model.objects.count() for model in models}, 'digest': digest}
state = snapshot()
if BACKUP:
    backup_path = Path(settings.OPENCOACH_DATA_DIR) if hasattr(settings, 'OPENCOACH_DATA_DIR') else settings.DATA_DIR
    backup_path = backup_path / 'backups' / ('verified-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
    call_command('backup_db', output=str(backup_path), stdout=io.StringIO())
    with tempfile.TemporaryDirectory(prefix='restore-check-', dir=settings.DATA_DIR) as directory:
        assert Path(directory).resolve().parent == settings.DATA_DIR.resolve()
        restored = Path(directory) / 'db.sqlite3'
        with closing(sqlite3.connect(backup_path.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(restored)) as target:
                source.backup(target)
                assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert not target.execute('PRAGMA foreign_key_check').fetchall()
        original = connection.settings_dict['NAME']
        connection.close()
        connection.settings_dict['NAME'] = str(restored)
        try:
            assert snapshot() == state
        finally:
            connection.close()
            connection.settings_dict['NAME'] = original
    print('backup_restore_orm=PASS')
    print('backup_path=' + str(backup_path))
print('SNAPSHOT=' + base64.b64encode(json.dumps(state, ensure_ascii=False, sort_keys=True).encode()).decode())
'''

def state_command(compose, backup):
    code = ('BACKUP=' + str(backup) + '\n' + SNAPSHOT_CODE).encode()
    encoded = base64.b64encode(code).decode()
    return compose + 'exec -T web python -c \'import base64;exec(base64.b64decode("' + encoded + '"))\''

def parse_state(output):
    value = output.rsplit('SNAPSHOT=', 1)[1].splitlines()[0]
    return json.loads(base64.b64decode(value))

def main():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(PinnedHostKey())
    password = getpass.getpass('SSH password (not saved): ')
    try:
        client.connect(HOST, port=22, username=USERNAME, password=password,
                       timeout=20, auth_timeout=20, look_for_keys=False, allow_agent=False)
        del password
        key = client.get_transport().get_remote_server_key()
        actual = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if actual != FINGERPRINT:
            raise RuntimeError('服务器主机指纹不匹配')
        compose = f'cd {TARGET} && docker compose -p opencoach-test '
        run(client, compose + 'exec -T web python manage.py test --noinput -v 1', 'linux-tests')
        before = parse_state(run(client, state_command(compose, True), 'backup-and-restore'))
        run(client, compose + 'restart web', 'restart')
        run(client, compose + 'up -d --wait --wait-timeout 120', 'health-after-restart')
        after = parse_state(run(client, state_command(compose, False), 'database-after-restart'))
        if after != before:
            raise RuntimeError('业务数据在重启前后不一致')
        print('restart_persistence=PASS', flush=True)
        status = run(client, "docker inspect qidu-mall-h5-web --format '{{.State.Health.Status}}'", 'existing-website')
        if status.strip() != 'healthy':
            raise RuntimeError('已有网站未通过健康检查')
        run(client, "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'", 'containers')
    finally:
        client.close()

if __name__ == '__main__':
    main()
