import json
from pathlib import PurePosixPath
import stat

ROOT_FILES = {'manage.py', 'requirements.txt', 'Dockerfile', 'compose.yaml', 'Caddyfile', 'entrypoint.sh',
              '.dockerignore', '.env.example', 'README.md', 'tools/deploy_support.py', 'tools/deploy_checks.py'}
SOURCE_DIRS = {'coaching', 'opencoach', 'templates', 'static'}
FRONTEND_FILES = {'frontend/package.json','frontend/package-lock.json','frontend/index.html',
                  'frontend/tsconfig.json','frontend/vite.config.ts'}

def validate_env(text):
    if len(text) > 65536:
        raise RuntimeError('应用配置文件过大')
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise RuntimeError('应用配置格式无效')
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('\"\'')
    if values.get('OPENCOACH_PORT') != '8001' or values.get('DJANGO_DEBUG') != '0':
        raise RuntimeError('测试部署配置必须使用端口8001且关闭DEBUG')
    if len(values.get('DJANGO_SECRET_KEY', '')) < 32:
        raise RuntimeError('独立应用密钥必须至少32个字符')
    if 'coach.qtedu.ac.cn' not in values.get('DJANGO_ALLOWED_HOSTS', '').split(','):
        raise RuntimeError('测试主机未列入ALLOWED_HOSTS')
    if 'https://coach.qtedu.ac.cn' not in values.get('DJANGO_CSRF_ORIGINS', '').split(','):
        raise RuntimeError('测试入口未列入CSRF来源')
    if values.get('OPENCOACH_DATA_DIR', '/app/data') != '/app/data':
        raise RuntimeError('应用数据路径必须为独立挂载目录/app/data')
    if values.get('DJANGO_SECURE_COOKIES') != '1':
        raise RuntimeError('HTTPS域名入口必须开启Secure Cookie')

def source_name(name):
    if not isinstance(name, str):
        raise RuntimeError('源码清单格式无效')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts or '\\' in name:
        raise RuntimeError('源码清单路径越界')
    if name != '.env.example' and (any(part in {'.env','.git','node_modules','__pycache__'} or part.startswith('.env.') for part in path.parts)
                                  or path.suffix.lower() in {'.pem','.key','.sqlite3','.map','.pyc'}):
        raise RuntimeError('源码清单不能包含私密配置、数据或构建缓存')
    if path.parts[0] == 'frontend':
        allowed = name in FRONTEND_FILES or name == 'frontend/dist/index.html'
        if len(path.parts)>2 and path.parts[1]=='src':
            allowed = path.suffix in {'.vue','.ts','.css','.svg'} and not any(part.startswith('.') for part in path.parts[2:])
        if len(path.parts)>4 and path.parts[1:4] == ('dist','static','h5'):
            allowed = path.suffix in {'.js','.css','.svg','.png','.jpg','.webp','.woff2'} and not any(part.startswith('.') for part in path.parts[4:])
        if not allowed:
            raise RuntimeError('前端清单不能包含配置、依赖目录或源映射')
        return path
    if name not in ROOT_FILES and path.parts[0] not in SOURCE_DIRS:
        raise RuntimeError('源码清单不能包含配置或数据文件')
    return path

def frontend_files(root):
    files = [root / name for name in sorted(FRONTEND_FILES)]
    for folder in ['frontend/src','frontend/dist']:
        for item in (root / folder).rglob('*'):
            if item.is_file():
                name = item.relative_to(root).as_posix()
                source_name(name)
                if item.is_symlink():
                    raise RuntimeError('不上传前端符号链接')
                files.append(item)
    return files

def validate_frontend_build(root):
    import re
    folder = root / 'frontend' / 'dist'
    index = folder / 'index.html'
    if not index.is_file() or index.is_symlink() or folder.resolve() != folder.absolute():
        raise RuntimeError('请先构建前端生产版本')
    html = index.read_text(encoding='utf-8')
    if '/src/' in html or 'localhost:' in html or 'impeccable' in html.lower():
        raise RuntimeError('前端入口包含开发脚本或本地注入')
    assets = re.findall(r'(?:src|href)="(/static/h5/[^"\s]+)"',html)
    if not assets or not any(name.endswith('.js') for name in assets):
        raise RuntimeError('前端入口未引用生产脚本')
    for name in assets:
        source_name('frontend/dist' + name)
        file = folder / name.lstrip('/')
        if not file.is_file() or file.is_symlink():
            raise RuntimeError('前端入口引用了缺失资源')
    return assets

def frontend_env(text, flag):
    import re
    validate_env(text)
    if flag not in [0,1]:
        raise RuntimeError('前端开关只接受0或1')
    setting = 'OPENCOACH_FRONTEND_ENABLED=' + str(flag)
    if re.search(r'^\s*OPENCOACH_FRONTEND_ENABLED\s*=',text,re.M):
        return re.sub(r'^\s*OPENCOACH_FRONTEND_ENABLED\s*=.*$',setting,text,flags=re.M).rstrip()+'\n'
    return text.rstrip()+'\n'+setting+'\n'

def sync_manifest(sftp, target, files):
    manifest = target + '/.source-files.json'
    try:
        info = sftp.lstat(manifest)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError('源码清单不能是符号链接或目录')
        with sftp.open(manifest, 'r') as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            raise RuntimeError('源码清单过大')
        previous = json.loads(raw)
    except FileNotFoundError:
        previous = []
    if not isinstance(previous, list):
        raise RuntimeError('源码清单格式无效')
    for name in [*previous, *files]:
        source_name(name)
    removals = []
    for name in sorted(set(previous) - set(files)):
        path = source_name(name)
        absolute = target + '/' + name
        try:
            info = sftp.lstat(absolute)
        except FileNotFoundError:
            continue
        parent = target if str(path.parent) == '.' else target + '/' + str(path.parent)
        if not stat.S_ISREG(info.st_mode) or sftp.normalize(parent) != parent:
            raise RuntimeError('拒绝清理被替换为符号链接的源码路径')
        removals.append(absolute)
    if removals:
        print('[source-cleanup] only obsolete uploaded files: ' + ', '.join(removals), flush=True)
    for path in removals:
        sftp.remove(path)
    with sftp.open(manifest, 'w') as handle:
        handle.write(json.dumps(sorted(files)))
