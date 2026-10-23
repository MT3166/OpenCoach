from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from opencoach.instance import cookie_names
from .helpers import make_student

class InstanceCookieTests(TestCase):
    def test_two_instances_keep_independent_browser_logins(self):
        coach = get_user_model().objects.create(username='coach', is_staff=True)
        student = make_student('member')
        session_a, csrf_a = cookie_names('independent-coach-a')
        session_b, csrf_b = cookie_names('independent-coach-b')
        browser = Client()
        other = Client()
        with override_settings(SESSION_COOKIE_NAME=session_a, CSRF_COOKIE_NAME=csrf_a):
            browser.force_login(coach)
        with override_settings(SESSION_COOKIE_NAME=session_b, CSRF_COOKIE_NAME=csrf_b):
            other.force_login(student.user)
        browser.cookies.update(other.cookies)
        with override_settings(SESSION_COOKIE_NAME=session_a, CSRF_COOKIE_NAME=csrf_a):
            data = browser.get('/api/v1/session/').json()['data']
            self.assertEqual(data['user']['id'],coach.id)
            self.assertEqual(data['user']['role'],'coach')
        with override_settings(SESSION_COOKIE_NAME=session_b, CSRF_COOKIE_NAME=csrf_b):
            data = browser.get('/api/v1/session/').json()['data']
            self.assertEqual(data['user']['id'],student.user_id)
            self.assertEqual(data['user']['role'],'student')

    def test_second_instance_does_not_break_first_csrf_form(self):
        coach = get_user_model().objects.create(username='coach', is_staff=True)
        student = make_student('member')
        csrf_a = cookie_names('independent-a')[1]
        csrf_b = cookie_names('independent-b')[1]
        browser = Client(enforce_csrf_checks=True)
        other = Client(enforce_csrf_checks=True)
        with override_settings(SESSION_COOKIE_NAME='test_session_a', CSRF_COOKIE_NAME=csrf_a):
            browser.force_login(coach)
            token = browser.get('/api/v1/session/').json()['data']['csrf_token']
        with override_settings(SESSION_COOKIE_NAME='test_session_b', CSRF_COOKIE_NAME=csrf_b):
            other.force_login(student.user)
            other.get('/api/v1/session/')
        browser.cookies.update(other.cookies)
        with override_settings(SESSION_COOKIE_NAME='test_session_a', CSRF_COOKIE_NAME=csrf_a):
            response = browser.post('/api/v1/coach/students/', {'name': '新学员'},
                                    content_type='application/json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 201)
