import json
from pathlib import Path
import tempfile
from django.test import SimpleTestCase
from tools.deploy_support import validate_env, sync_manifest, source_name

TARGET = '/root/opencoach-test'

class LocalSFTP:
    def __init__(self, root):
        self.root = root

    def path(self, remote):
        return self.root / Path(remote).relative_to(TARGET)

    def open(self, path, mode):
        return self.path(path).open(mode, encoding='utf-8')

    def lstat(self, path):
        return self.path(path).lstat()

    def normalize(self, path):
        relative = self.path(path).resolve().relative_to(self.root.resolve()).as_posix()
        return TARGET if relative == '.' else TARGET + '/' + relative

    def remove(self, path):
        self.path(path).unlink()

class DeploymentSupportTests(SimpleTestCase):
    def test_build_validation_catches_a_missing_asset(self):
        from tools.deploy_support import validate_frontend_build
        with tempfile.TemporaryDirectory(prefix='opencoach-build-check-') as directory:
            root=Path(directory)
            (root/'frontend/dist').mkdir(parents=True)
            (root/'frontend/dist/index.html').write_text('<script src="/static/h5/main-Abc12345.js"></script>',encoding='utf-8')
            with self.assertRaises(RuntimeError):
                validate_frontend_build(root)
            (root/'frontend/dist/static/h5').mkdir(parents=True)
            (root/'frontend/dist/static/h5/main-Abc12345.js').write_text('production',encoding='utf-8')
            self.assertEqual(validate_frontend_build(root),['/static/h5/main-Abc12345.js'])

    def test_frontend_flag_preserves_existing_configuration(self):
        from tools.deploy_support import frontend_env
        original=self.env()+'COACH_NAME=林教练\n'
        changed=frontend_env(original,1)
        self.assertIn('COACH_NAME=林教练\n',changed)
        self.assertIn('OPENCOACH_FRONTEND_ENABLED=1\n',changed)
        self.assertEqual(frontend_env(changed,0).count('OPENCOACH_FRONTEND_ENABLED='),1)

    def test_frontend_source_and_artifacts_are_allowed(self):
        for name in ['frontend/package.json','frontend/package-lock.json','frontend/src/pages/CoachRecord.vue','frontend/dist/index.html','frontend/dist/static/h5/index-Abc12345.js']:
            with self.subTest(name=name):
                self.assertEqual(source_name(name).as_posix(),name)

    def test_frontend_private_and_dependency_paths_are_rejected(self):
        for name in ['frontend/.env','frontend/src/.env','frontend/node_modules/vue/index.js','frontend/.git/config','frontend/dist/static/h5/private.js.map','frontend/dist/../../data/db.sqlite3']:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                source_name(name)

    def test_nested_backend_secrets_are_rejected(self):
        for name in ['coaching/.env','opencoach/.env.local','static/private.key','coaching/dump.sqlite3','static/app.js.map']:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                source_name(name)

    def env(self, port='8001', debug='0', secret='x' * 48, cookies='1'):
        return f'DJANGO_SECRET_KEY={secret}\nOPENCOACH_PORT={port}\nDJANGO_DEBUG={debug}\nDJANGO_ALLOWED_HOSTS=coach.qtedu.ac.cn\nDJANGO_CSRF_ORIGINS=https://coach.qtedu.ac.cn\nDJANGO_SECURE_COOKIES={cookies}\n'

    def test_existing_wrong_port_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_env(self.env(port='80'))

    def test_existing_debug_environment_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_env(self.env(debug='1'))

    def test_empty_existing_secret_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_env(self.env(secret=''))

    def test_valid_existing_settings_can_be_reused(self):
        validate_env(self.env())

    def test_previous_server_settings_are_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_env(self.env().replace('coach.qtedu.ac.cn', '192.3.233.180'))

    def test_https_deployment_requires_secure_cookies(self):
        with self.assertRaises(RuntimeError):
            validate_env(self.env(cookies='0'))

    def test_insecure_csrf_origin_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_env(self.env().replace('https://coach.qtedu.ac.cn', 'http://coach.qtedu.ac.cn'))

    def test_only_previously_uploaded_obsolete_source_is_removed(self):
        with tempfile.TemporaryDirectory(prefix='opencoach-deploy-test-') as temporary:
            root = Path(temporary)
            (root / 'coaching').mkdir()
            (root / 'data').mkdir()
            (root / 'coaching/old.py').write_text('obsolete', encoding='utf-8')
            (root / 'coaching/new.py').write_text('current', encoding='utf-8')
            (root / 'coaching/user-note.txt').write_text('untracked', encoding='utf-8')
            (root / 'data/db.sqlite3').write_text('saved data', encoding='utf-8')
            (root / '.env').write_text('saved configuration', encoding='utf-8')
            (root / '.source-files.json').write_text(json.dumps(['coaching/old.py']), encoding='utf-8')
            sync_manifest(LocalSFTP(root), TARGET, ['coaching/new.py'])
            self.assertFalse((root / 'coaching/old.py').exists())
            self.assertTrue((root / 'coaching/new.py').exists())
            self.assertEqual((root / 'coaching/user-note.txt').read_text(), 'untracked')
            self.assertEqual((root / 'data/db.sqlite3').read_text(), 'saved data')
            self.assertEqual((root / '.env').read_text(), 'saved configuration')

    def test_manifest_cannot_target_persistent_data(self):
        with tempfile.TemporaryDirectory(prefix='opencoach-deploy-test-') as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            (root / 'data/db.sqlite3').write_text('saved data', encoding='utf-8')
            (root / '.source-files.json').write_text(json.dumps(['data/db.sqlite3']), encoding='utf-8')
            with self.assertRaises(RuntimeError):
                sync_manifest(LocalSFTP(root), TARGET, [])
            self.assertEqual((root / 'data/db.sqlite3').read_text(), 'saved data')
