import tempfile
from pathlib import Path
from django.test import SimpleTestCase, override_settings

class FrontendTests(SimpleTestCase):
    def test_enabled_routes_return_plain_index_without_private_data(self):
        with tempfile.TemporaryDirectory(prefix='opencoach-spa-test-') as directory:
            root=Path(directory)
            (root/'index.html').write_text('<html><div id="app">Vue entry</div></html>',encoding='utf-8')
            with override_settings(OPENCOACH_FRONTEND_ENABLED=True,FRONTEND_DIST=root):
                for path in ['/','/login/','/coach/lessons/new/','/coach/students/1/','/student/plans/1/']:
                    with self.subTest(path=path):
                        response=self.client.get(path)
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(b''.join(response.streaming_content),b'<html><div id="app">Vue entry</div></html>')
                        self.assertEqual(response['Cache-Control'],'no-store')

    @override_settings(OPENCOACH_FRONTEND_ENABLED=True)
    def test_api_static_and_unknown_routes_do_not_return_spa(self):
        for path in ['/api/v1/not-real/','/static/h5/missing.js','/coach/not-real/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.post('/coach/lessons/new/',{}).status_code,405)

    def test_missing_frontend_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory(prefix='opencoach-spa-missing-') as directory:
            with override_settings(OPENCOACH_FRONTEND_ENABLED=True,FRONTEND_DIST=Path(directory)):
                self.assertEqual(self.client.get('/login/').status_code,503)
