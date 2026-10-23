from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from coaching import accounts

class ApiAuthTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create_user('api-coach', password='Exercise-74!', is_staff=True)
        self.strict = Client(enforce_csrf_checks=True)

    def token(self):
        response = self.strict.get('/api/v1/session/')
        self.assertEqual(response.status_code, 200)
        return response.json()['data']['csrf_token']

    def test_anonymous_session_contains_brand_but_no_private_data(self):
        response = self.client.get('/api/v1/session/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['data']['user'])
        self.assertNotIn('students', response.json()['data'])

    def test_session_response_cannot_be_reused_from_browser_cache(self):
        self.assertEqual(self.client.get('/api/v1/session/')['Cache-Control'],'no-store')

    @override_settings(BRAND_NAME='松间训练', COACH_NAME='林教练')
    def test_instance_brand_is_used(self):
        self.assertEqual(self.client.get('/api/v1/session/').json()['data']['brand']['display_name'], '松间训练')

    def test_missing_csrf_cannot_login(self):
        response = self.strict.post('/api/v1/auth/login/', {'username':'api-coach', 'password':'Exercise-74!'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error']['code'], 'csrf_failed')

    def test_login_rotates_csrf_and_logout_rejects_old_token(self):
        before = self.token()
        response = self.strict.post('/api/v1/auth/login/', {'username':'api-coach','password':'Exercise-74!'}, content_type='application/json', HTTP_X_CSRFTOKEN=before)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['user']['role'], 'coach')
        after = response.json()['data']['csrf_token']
        bad = self.strict.post('/api/v1/auth/logout/', {}, content_type='application/json', HTTP_X_CSRFTOKEN=before)
        self.assertEqual(bad.status_code, 403)
        good = self.strict.post('/api/v1/auth/logout/', {}, content_type='application/json', HTTP_X_CSRFTOKEN=after)
        self.assertEqual(good.status_code, 200)
        self.assertIsNone(good.json()['data']['user'])

    def test_wrong_password_is_json_401(self):
        response = self.client.post('/api/v1/auth/login/', {'username':'api-coach','password':'wrong'}, content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'invalid_credentials')

    def test_unknown_api_is_json_even_in_debug(self):
        with override_settings(DEBUG=True):
            response = self.client.get('/api/v1/does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')

    def test_invitation_registration_enforces_csrf(self):
        token = accounts.issue_invite(accounts.create_student('新学员'))
        response = self.strict.post(f'/api/v1/invitations/{token}/accept/', {'username':'new-member','password':'Exercise-74!','password_confirm':'Exercise-74!'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_invitation_registers_student_once(self):
        student = accounts.create_student('新学员')
        token = accounts.issue_invite(student)
        response = self.client.post(f'/api/v1/invitations/{token}/accept/', {'username':'new-member','password':'Exercise-74!','password_confirm':'Exercise-74!'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['data']['user']['role'], 'student')
        self.client.logout()
        self.assertEqual(self.client.get(f'/api/v1/invitations/{token}/').status_code, 409)
