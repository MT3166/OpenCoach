"""Package reviewed application source only; verify entries against SHA256 manifest."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = ('coaching','opencoach','frontend','static','templates','tools','docs')
ROOT_FILES = ('.dockerignore','.env.example','.gitignore','Caddyfile','compose.yaml','Dockerfile',
              'entrypoint.sh','manage.py','requirements.txt','README.md','PRODUCT.md','CHANGELOG-five-stages.md')
EXCLUDED = {'.venv','node_modules','dist','staticfiles','__pycache__','.git','.moss-mem','artifacts','.impeccable'}


def allowed(path):
    relative = path.relative_to(ROOT)
    return (not path.is_symlink() and not EXCLUDED.intersection(relative.parts)
            and (not path.name.startswith('.env') or path.name == '.env.example')
            and not any(suffix in path.name.lower() for suffix in ('.sqlite','.db-wal','.db-shm'))
            and path.suffix.lower() not in {'.pyc','.pem','.key','.zip','.tar','.gz'})


def main():
    paths = [ROOT/name for name in ROOT_FILES]
    for directory in DIRECTORIES:
        paths.extend(path for path in (ROOT/directory).rglob('*') if path.is_file() and allowed(path))
    paths = sorted(paths,key=lambda path:path.relative_to(ROOT).as_posix())
    output = ROOT/'artifacts'/'OpenCoach-five-stages-source.zip'
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    hashes = {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path,path.relative_to(ROOT).as_posix())
        archive.writestr('SOURCE-MANIFEST.sha256',''.join(f'{digest}  {name}\n' for name,digest in hashes.items()))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(hashes) | {'SOURCE-MANIFEST.sha256'}
        for name,digest in hashes.items():
            assert allowed(ROOT/name), f'Forbidden path: {name}'
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest, f'Changed source: {name}'
        for name in ('frontend/package-lock.json','coaching/migrations/0005_waitlist.py','docs/requirements/stage-5.md','CHANGELOG-five-stages.md'):
            assert name in hashes, f'Missing source: {name}'
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.with_suffix('.zip.sha256')).write_text(f'{digest}  {output.name}\n',encoding='utf-8')
    print(f'PASS: {len(hashes)} source files; ZIP CRC, SHA256 and exclusions verified')
    print(f'{output}\n{digest}\n{output.stat().st_size} bytes')


if __name__ == '__main__':
    main()
