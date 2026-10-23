import json
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages, constants
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from coaching.models import Booking, Student, TrainingPlan, Submission
from .helpers import make_student, make_session

@override_settings(OPENCOACH_FRONTEND_ENABLED=False)
class ViewTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='coach', is_staff=True)
        self.student = make_student('xiaoyu')
        self.other = make_student('other')
        self.session = make_session()
        self.client.force_login(self.coach)
        self.student_client = Client()
        self.student_client.force_login(self.student.user)
        self.rows = [{'name': '深蹲', 'sets': 3, 'reps': 12}]
        self.plan = TrainingPlan.objects.create(student=self.student, title='今日核心练习',
            due_date=timezone.localdate(), exercises=self.rows)

    def test_teacher_can_create_student(self):
        response = self.client.post('/coach/students/', {'name': '新学员'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(name='新学员').exists())

    @override_settings(ALLOWED_HOSTS=['coach.qtedu.ac.cn'])
    def test_invitation_uses_https_behind_domain_proxy(self):
        student = Student.objects.create(name='待邀请学员')
        response = self.client.post(f'/coach/students/{student.id}/', {'action': 'invite'},
            HTTP_HOST='coach.qtedu.ac.cn', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['invite_url'].startswith('https://coach.qtedu.ac.cn/invite/'))

    def test_booking_is_visible_to_teacher(self):
        response = self.student_client.post('/student/sessions/',
            {'session_id': self.session.id, 'operation_key': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.filter(student=self.student, session=self.session).count(), 1)
        self.assertContains(self.client.get(f'/coach/sessions/{self.session.id}/'), 'xiaoyu')

    def test_student_cannot_open_teacher_console(self):
        self.assertEqual(self.student_client.get('/coach/').status_code, 403)

    def test_other_student_plan_is_not_disclosed(self):
        self.student_client.force_login(self.other.user)
        self.assertEqual(self.student_client.get(f'/student/plans/{self.plan.id}/').status_code, 404)

    def test_unauthenticated_booking_does_not_write(self):
        response = Client().post('/student/sessions/',
            {'session_id': self.session.id, 'operation_key': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), 0)

    def test_submit_and_review_through_pages(self):
        response = self.student_client.post(f'/student/plans/{self.plan.id}/',
            {'exercises': json.dumps(self.rows), 'note': '全部完成', 'intent': 'submit'})
        self.assertEqual(response.status_code, 302)
        submission = Submission.objects.filter(plan=self.plan).first()
        self.assertIsNotNone(submission)
        response = self.client.post(f'/coach/plans/{self.plan.id}/', {'feedback': '保持稳定，明天继续。'})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.student_client.get(f'/student/plans/{self.plan.id}/'), '保持稳定，明天继续。')

    def test_mobile_home_is_served(self):
        response = self.student_client.get('/student/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'viewport')

    def test_missing_csrf_cannot_create_booking(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.student.user)
        self.assertEqual(strict.post('/student/sessions/',
            {'session_id': self.session.id, 'operation_key': str(uuid.uuid4())}).status_code, 403)

    def test_cancelled_request_retry_does_not_claim_a_new_reserved_seat(self):
        key = uuid.uuid4()
        Booking.objects.create(student=self.student, session=self.session,
                               status='cancelled', operation_key=key)
        response = self.student_client.post('/student/sessions/',
            {'session_id': self.session.id, 'operation_key': str(key)}, follow=True)
        levels = [message.level for message in get_messages(response.wsgi_request)]
        self.assertNotIn(constants.SUCCESS, levels)
        self.assertIn(constants.INFO, levels)
        self.assertContains(response, '已取消')
        self.assertEqual(Booking.objects.filter(status='booked').count(), 0)
