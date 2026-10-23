"""项目专用 SSH 部署工具。使用本机已有的 paramiko，不保存连接密码。"""
import argparse
import base64
import codecs
import getpass
import hashlib
from pathlib import Path
import secrets
import stat
import sys
import tarfile
import tempfile
import time
import shlex
from datetime import datetime, timezone
import paramiko
from deploy_support import sync_manifest, validate_env, frontend_files, validate_frontend_build, frontend_env
from deploy_checks import COMPARE_CODE, PREFLIGHT_NEW, PREFLIGHT_OLD

HOST = '101.201.244.115'
USERNAME = 'root'
TARGET = '/root/opencoach-test'
FINGERPRINT = 'YBehY7BrQ9chKp3XfnXLNA4fij9Z0KIvF6agoDpSf08'
ROOT = Path(__file__).resolve().parent.parent

class PinnedHostKey(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        digest = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if digest != FINGERPRINT:
            raise paramiko.SSHException('服务器主机指纹不匹配')

def run(client, command, label='remote', timeout=900):
    print(f'[{label}]', flush=True)
    _, stdout, _ = client.exec_command(command, timeout=timeout)
    channel = stdout.channel
    channel.set_combine_stderr(True)
    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    output = []
    deadline = time.monotonic() + timeout
    while not channel.exit_status_ready() or channel.recv_ready():
        if time.monotonic() > deadline:
            channel.close()
            raise RuntimeError(f'{label}: timeout')
        if channel.recv_ready():
            text = decoder.decode(channel.recv(8192))
            output.append(text)
            sys.stdout.write(text)
            sys.stdout.flush()
        else:
            time.sleep(.15)
    remainder = decoder.decode(b'', final=True)
    output.append(remainder)
    sys.stdout.write(remainder)
    code = channel.recv_exit_status()
    if code:
        raise RuntimeError(f'{label}: exit {code}')
    return ''.join(output)

def upload(client):
    validate_frontend_build(ROOT)
    with client.open_sftp() as sftp:
        if sftp.normalize('/root') != '/root':
            raise RuntimeError('部署父目录必须为 /root')
        try:
            info = sftp.lstat(TARGET)
            if not stat.S_ISDIR(info.st_mode):
                raise RuntimeError('部署路径不是独立目录')
        except FileNotFoundError:
            sftp.mkdir(TARGET, mode=0o700)
        marker = TARGET + '/.opencoach-test'
        try:
            if not stat.S_ISREG(sftp.lstat(marker).st_mode):
                raise RuntimeError('部署目录标记无效')
        except FileNotFoundError:
            if sftp.listdir(TARGET):
                raise RuntimeError('目标目录已有其他内容，停止覆写')
            with sftp.open(marker, 'wx') as handle:
                handle.write('OpenCoach test deployment v1')
        files = [ROOT / name for name in ['manage.py', 'requirements.txt', 'Dockerfile',
            'compose.yaml', 'Caddyfile', 'entrypoint.sh', '.dockerignore', '.env.example', 'README.md', 'tools/deploy_support.py', 'tools/deploy_checks.py']]
        for directory in ['coaching', 'opencoach', 'templates', 'static']:
            files.extend(path for path in (ROOT / directory).rglob('*')
                         if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
        from deploy_support import source_name
        for path in files:
            source_name(path.relative_to(ROOT).as_posix())
        files.extend(frontend_files(ROOT))
        with tempfile.TemporaryDirectory(prefix='opencoach-upload-') as temporary:
            archive = Path(temporary) / 'source.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                for path in files:
                    if path.is_symlink():
                        raise RuntimeError('不上传符号链接')
                    bundle.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
            sftp.put(str(archive), TARGET + '/source.tar.gz')
        print(f'[upload] {len(files)} project files', flush=True)
    run(client, f'tar -xzf {TARGET}/source.tar.gz -C {TARGET}', 'extract')
    with client.open_sftp() as sftp:
        sync_manifest(sftp, TARGET, [path.relative_to(ROOT).as_posix() for path in files])

def configure(client):
    with client.open_sftp() as sftp:
        try:
            if not stat.S_ISDIR(sftp.lstat(TARGET + '/data').st_mode):
                raise RuntimeError('应用数据路径不是独立目录')
        except FileNotFoundError:
            sftp.mkdir(TARGET + '/data', mode=0o700)
        sftp.chown(TARGET + '/data', 1000, 1000)
        try:
            if not stat.S_ISREG(sftp.lstat(TARGET + '/.env').st_mode):
                raise RuntimeError('应用配置不能是符号链接或目录')
            with sftp.open(TARGET + '/.env', 'r') as handle:
                existing = handle.read(65537).decode('utf-8')
            validate_env(existing)
        except FileNotFoundError:
            values = '\n'.join([
                'DJANGO_SECRET_KEY=' + secrets.token_urlsafe(48),
                'DJANGO_DEBUG=0', 'DJANGO_ALLOWED_HOSTS=coach.qtedu.ac.cn,127.0.0.1,localhost',
                'DJANGO_CSRF_ORIGINS=https://coach.qtedu.ac.cn', 'DJANGO_SECURE_COOKIES=1',
                'OPENCOACH_PORT=8001', 'COACH_NAME=林屿教练', 'BRAND_NAME=OpenCoach', '',
            ])
            validate_env(values)
            with sftp.open(TARGET + '/.env', 'wx') as handle:
                handle.write(values.encode('utf-8'))
            sftp.chmod(TARGET + '/.env', 0o600)
    print('[configuration] isolated application settings ready', flush=True)

def preflight(client):
    ports = run(client, "ss -H -ltn '( sport = :8001 )'", 'port-check')
    if ports.strip():
        owned = run(client,
            "docker ps --filter label=com.docker.compose.project=opencoach-test --format '{{.Ports}}'",
            'existing-test-instance')
        if ':8001->' not in owned:
            raise RuntimeError('8001 已被其他服务使用，停止部署')

def set_frontend(client, flag):
    if flag is None:
        return
    with client.open_sftp() as sftp:
        with sftp.open(TARGET+'/.env','r') as handle:
            current=handle.read(65537).decode('utf-8')
        content=frontend_env(current,flag)
        staging=TARGET+'/.env-next-'+secrets.token_hex(4)
        with sftp.open(staging,'wx') as handle:
            handle.write(content.encode('utf-8'))
        sftp.chmod(staging,0o600)
        sftp.posix_rename(staging,TARGET+'/.env')
    print('[frontend] entry setting updated after successful image build',flush=True)

def encoded_python(code):
    payload=base64.b64encode(code.encode()).decode()
    return 'python -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(payload)+'))')

def deployment_preflight(client, backup, stamp, prior):
    folder=TARGET+'/data/preflight-'+stamp
    host_backup=TARGET+'/data/backups/'+backup.rsplit('/',1)[1]
    with client.open_sftp() as sftp:
        if sftp.normalize(TARGET+'/data') != TARGET+'/data':
            raise RuntimeError('预检数据父目录不能是符号链接')
        sftp.mkdir(folder,mode=0o700)
        sftp.chown(folder,1000,1000)
    run(client,'cp '+shlex.quote(host_backup)+' '+shlex.quote(folder+'/db.sqlite3')+' && cp '+shlex.quote(host_backup)+' '+shlex.quote(folder+'/original.sqlite3'),'isolated-migration-copy')
    with client.open_sftp() as sftp:
        for name in ['db.sqlite3','original.sqlite3']:
            sftp.chown(folder+'/'+name,1000,1000)
            sftp.chmod(folder+'/'+name,0o600)
    base='cd '+TARGET+' && docker run --rm --network none --env-file .env -e OPENCOACH_FRONTEND_ENABLED='
    mount=' -v '+shlex.quote(folder+':/app/data')+' '
    run(client,base+'1'+mount+'opencoach-test-web '+encoded_python(COMPARE_CODE+PREFLIGHT_NEW),'new-image-preflight')
    run(client,base+'0'+mount+shlex.quote(prior)+' '+encoded_python(PREFLIGHT_OLD),'rollback-compatibility-preflight')
    print('[preflight] isolated copy retained at '+folder,flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['deploy', 'upload', 'command'])
    parser.add_argument('--command')
    parser.add_argument('--frontend',type=int,choices=[0,1])
    parser.add_argument('--build-proxy')
    args = parser.parse_args()
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(PinnedHostKey())
    password = getpass.getpass('SSH password (not saved): ')
    try:
        client.connect(HOST, port=22, username=USERNAME, password=password,
                       timeout=20, auth_timeout=20, look_for_keys=False, allow_agent=False)
        del password
        key = client.get_transport().get_remote_server_key()
        digest = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if digest != FINGERPRINT:
            raise RuntimeError('服务器主机指纹不匹配')
        if args.action in ['deploy', 'upload']:
            preflight(client)
            upload(client)
        if args.action == 'deploy':
            configure(client)
            compose = f'cd {TARGET} && docker compose -p opencoach-test '
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            prior=run(client,"docker inspect opencoach-test-web-1 --format '{{.Image}}'",'retain-current-image').strip()
            run(client,'docker tag '+shlex.quote(prior)+' opencoach-test-web:retained-'+stamp,'tag-rollback-image')
            if args.build_proxy:
                proxy=shlex.quote(args.build_proxy)
                run(client,f'cd {TARGET} && docker build --network=host --build-arg HTTP_PROXY={proxy} --build-arg HTTPS_PROXY={proxy} -t opencoach-test-web .','build')
            else:
                run(client, compose + 'build', 'build')
            backup='/app/data/backups/before-formal-'+stamp+'.sqlite3'
            run(client,compose+'exec -T web python manage.py backup_db --output '+backup,'backup-before-migration')
            deployment_preflight(client,backup,stamp,prior)
            final_backup='/app/data/backups/cutover-formal-'+stamp+'.sqlite3'
            run(client,compose+'exec -T web python manage.py backup_db --output '+final_backup,'final-cutover-backup')
            with client.open_sftp() as sftp:
                with sftp.open(TARGET+'/.env','r') as handle:
                    config=handle.read(65537).decode('utf-8')
            previous_flag=1 if any(line.strip()=='OPENCOACH_FRONTEND_ENABLED=1' for line in config.splitlines()) else 0
            set_frontend(client,args.frontend)
            try:
                run(client, compose + 'up -d --wait --wait-timeout 120', 'start')
            except Exception:
                print('[rollback] new service did not pass health; restoring proven-compatible previous image',flush=True)
                run(client,'docker tag '+shlex.quote(prior)+' opencoach-test-web','restore-image')
                set_frontend(client,previous_flag)
                run(client,compose+'up -d --no-build --force-recreate --wait --wait-timeout 120 web','restore-service')
                raise
            code=COMPARE_CODE+'\nfrom pathlib import Path\ncompare_legacy(Path('+repr(final_backup)+'),Path("/app/data/db.sqlite3"))\n'
            run(client,compose+'exec -T web '+encoded_python(code),'preserved-live-data')
            run(client, compose + 'ps', 'status')
            print('[release] backup='+final_backup+' retained=opencoach-test-web:retained-'+stamp,flush=True)
        elif args.action == 'command':
            if not args.command:
                raise RuntimeError('--command is required')
            run(client, args.command)
    finally:
        client.close()

if __name__ == '__main__':
    main()
