import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from coaching import booking
from coaching.models import Booking
from .helpers import make_student, make_session


class WaitlistTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='queue-coach', is_staff=True)
        self.occupant = make_student('queue-occupant')
        self.first = make_student('queue-first')
        self.second = make_student('queue-second')
        self.course = make_session()
        self.booked = booking.reserve(self.occupant, self.course.pk, uuid.uuid4())

    def join(self, student, key=None):
        self.client.force_login(student.user)
        response = self.client.post(f'/api/v1/student/sessions/{self.course.pk}/waitlist/',
            {'operation_key':str(key or uuid.uuid4())}, content_type='application/json')
        self.assertIn(response.status_code, (200, 201), response.content)
        return response.json()['data']

    def test_fifo_promotion_is_one_booking_one_hold_and_retry_safe(self):
        key = uuid.uuid4()
        first = self.join(self.first, key)
        self.assertEqual(self.join(self.first, key)['id'], first['id'])
        second = self.join(self.second)
        booking.cancel(self.booked.pk, self.coach)
        booking.cancel(self.booked.pk, self.coach)
        result = Booking.objects.get(student=self.first, session=self.course)
        self.assertEqual(result.status, 'booked')
        self.assertEqual(booking.balances(self.first, 'private')['reserved'], 1)
        self.client.force_login(self.second.user)
        self.assertEqual(self.client.get('/api/v1/student/waitlist/').json()['data']['items'][0]['id'], second['id'])
        self.client.force_login(self.coach)
        queue = self.client.get(f'/api/v1/coach/sessions/{self.course.pk}/waitlist/').json()['data']['items']
        self.assertEqual([row['status'] for row in queue], ['promoted', 'waiting'])

    def test_expired_head_is_skipped(self):
        self.join(self.first)
        self.join(self.second)
        self.first.credits.update(expires_on=timezone.localdate()-timedelta(days=1))
        booking.cancel(self.booked.pk, self.coach)
        self.assertFalse(Booking.objects.filter(student=self.first).exists())
        self.assertEqual(Booking.objects.get(student=self.second).status, 'booked')

    def test_conflicting_head_is_skipped(self):
        self.join(self.first)
        self.join(self.second)
        booking.reserve(self.first, make_session(30.5).pk, uuid.uuid4())
        booking.cancel(self.booked.pk, self.coach)
        self.assertEqual(Booking.objects.get(student=self.second).session_id, self.course.pk)

    def test_exit_is_owned_and_does_not_cancel_promoted_booking(self):
        first = self.join(self.first)
        self.client.force_login(self.second.user)
        url = f"/api/v1/student/waitlist/{first['id']}/leave/"
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.first.user)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.join(self.second)
        booking.cancel(self.booked.pk, self.coach)
        self.client.force_login(self.first.user)
        row = self.client.get('/api/v1/student/waitlist/').json()['data']['items'][0]
        self.assertEqual(row['status'], 'cancelled')

    def test_whole_session_cancel_never_promotes(self):
        self.join(self.first)
        booking.cancel_session(self.course.pk, self.coach)
        self.assertFalse(Booking.objects.filter(student=self.first).exists())
        self.assertEqual(self.client.get('/api/v1/student/waitlist/').json()['data']['items'][0]['status'], 'cancelled')

    def test_reschedule_frees_seat_and_promotes(self):
        self.join(self.first)
        booking.reschedule(self.booked.pk, self.coach, make_session(35).pk, uuid.uuid4())
        self.assertTrue(Booking.objects.filter(student=self.first, session=self.course, status='booked').exists())

    def test_join_requires_full_future_course_and_unique_waiting(self):
        self.join(self.first)
        duplicate = self.client.post(f'/api/v1/student/sessions/{self.course.pk}/waitlist/', {'operation_key':str(uuid.uuid4())}, content_type='application/json')
        self.assertEqual(duplicate.status_code, 409)
        open_course = make_session(38)
        response = self.client.post(f'/api/v1/student/sessions/{open_course.pk}/waitlist/', {'operation_key':str(uuid.uuid4())}, content_type='application/json')
        self.assertEqual(response.status_code, 409)


class WaitlistConcurrencyTests(TransactionTestCase):
    def test_duplicate_release_promotes_only_first_waiter_with_file_sqlite(self):
        self.assertNotIn('memory', str(connection.settings_dict['NAME']))
        coach = get_user_model().objects.create(username='race-queue-coach', is_staff=True)
        occupant = make_student('race-queue-occupant')
        first, second = make_student('race-queue-first', credits=1), make_student('race-queue-second', credits=1)
        course = make_session()
        item = booking.reserve(occupant, course.pk, uuid.uuid4())
        from coaching.waitlist import join
        join(first, course.pk, uuid.uuid4())
        join(second, course.pk, uuid.uuid4())
        gate = Barrier(2)
        def release(_):
            close_old_connections()
            try:
                connection.ensure_connection()
                gate.wait(timeout=10)
                return booking.cancel(item.pk, coach).pk
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(release, (1, 2))), [item.pk, item.pk])
        self.assertEqual(Booking.objects.filter(session=course, status='booked').count(), 1)
        self.assertTrue(Booking.objects.filter(student=first, status='booked').exists())
        self.assertFalse(Booking.objects.filter(student=second).exists())
