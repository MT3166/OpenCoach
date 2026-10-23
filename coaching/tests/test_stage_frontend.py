import tempfile
from pathlib import Path
from django.test import SimpleTestCase, override_settings


class StageFrontendTests(SimpleTestCase):
    def test_batch_and_report_can_be_opened_directly_or_refreshed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'index.html').write_text('<div id="app">new pages</div>',encoding='utf-8')
            with override_settings(OPENCOACH_FRONTEND_ENABLED=True,FRONTEND_DIST=root):
                for path in ('/coach/lessons/batch/','/coach/reports/'):
                    with self.subTest(path=path):
                        response=self.client.get(path)
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(b''.join(response.streaming_content),b'<div id="app">new pages</div>')
