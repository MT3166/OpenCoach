import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from coaching import booking, lessons
from coaching.models import Booking, Session
from .helpers import make_student


class MonthlyReportTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='report-coach', is_staff=True)
        self.student = make_student('report-student', credits=10)
        self.client.force_login(self.coach)

    def course(self, start, status='completed', cancelled=False):
        course = Session.objects.create(title='月界测试', kind='private', start=datetime.fromisoformat(start),
            end=datetime.fromisoformat(start)+timedelta(hours=1), location='教室', capacity=1, cancelled=cancelled)
        return Booking.objects.create(student=self.student,session=course,status=status,operation_key=uuid.uuid4())

    def report(self, month):
        response = self.client.get('/api/v1/coach/reports/monthly/', {'month':month})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data']

    def test_shanghai_month_boundaries_statuses_and_rate(self):
        self.course('2026-09-30T15:59:59+00:00')
        self.course('2026-09-30T16:00:00+00:00')
        self.course('2026-10-31T15:59:59+00:00', 'no_show_charged')
        self.course('2026-10-31T16:00:00+00:00')
        self.course('2026-10-01T09:00:00+08:00', 'no_show_waived')
        self.course('2026-10-02T09:00:00+08:00', 'cancelled')
        self.course('2026-10-03T09:00:00+08:00', 'booked')
        self.course('2026-10-04T09:00:00+08:00', 'no_show_waived', cancelled=True)
        with patch('django.utils.timezone.now', return_value=datetime(2026,11,2,tzinfo=ZoneInfo('Asia/Shanghai'))):
            self.client.force_login(self.coach)
            data = self.report('2026-10')
        self.assertEqual([data[k] for k in ('scheduled_attended','scheduled_missed','scheduled_cancelled','pending')], [1,3,1,1])
        self.assertEqual(data['scheduled_rate'], 33.3)

    def test_direct_and_expired_counts_do_not_inflate_rate(self):
        expiry = date(2026,9,30)
        with patch('django.utils.timezone.now', return_value=datetime(2026,9,30,12,tzinfo=ZoneInfo('Asia/Shanghai'))):
            booking.add_credit(self.student,'private',3,uuid.uuid4(),expires_on=expiry)
            lessons.record_direct_lesson(self.student,self.coach,'private',expiry,'',uuid.uuid4())
        with patch('django.utils.timezone.now', return_value=datetime(2026,10,2,tzinfo=ZoneInfo('Asia/Shanghai'))):
            data = self.report('2026-10')
        self.assertEqual(data['credit_expired'], 2)
        self.assertEqual(data['direct_attended'], 0)
        self.assertEqual(self.report('2026-09')['direct_attended'], 1)
        self.assertEqual(data['scheduled_rate'], 0)

    def test_empty_and_bad_month_and_permissions(self):
        data = self.report('2020-02')
        self.assertTrue(all(value == 0 for key,value in data.items() if key != 'month'))
        for month in ('bad','2026-13','2026-1','9999-12'):
            response = self.client.get('/api/v1/coach/reports/monthly/', {'month':month})
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.json())
        self.client.force_login(self.student.user)
        self.assertEqual(self.client.get('/api/v1/coach/reports/monthly/?month=2026-10').status_code, 403)
