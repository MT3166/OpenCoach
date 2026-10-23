import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from coaching import booking
from coaching.models import Booking, CreditEntry, DirectLesson
from .helpers import make_student, make_session


class RescheduleBatchTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='stage-coach', is_staff=True)
        self.student = make_student('stage-student', credits=1)
        self.other = make_student('stage-other', credits=1)
        self.source = make_session(30)
        self.target = make_session(34)
        self.item = booking.reserve(self.student, self.source.pk, uuid.uuid4())

    def post(self, url, payload):
        return self.client.post('/api/v1/' + url, payload, content_type='application/json')

    def move(self, target=None, key=None, role='student'):
        return self.post(f'{role}/bookings/{self.item.pk}/reschedule/', {'session_id':(target or self.target).pk,'operation_key':str(key or uuid.uuid4())})

    def test_reschedule_transfers_last_credit_and_retries_same_result(self):
        self.client.force_login(self.student.user)
        key = uuid.uuid4()
        first = self.move(key=key)
        self.assertEqual(first.status_code, 200, first.content)
        again = self.move(key=key)
        self.assertEqual(first.json(), again.json())
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'cancelled')
        self.assertEqual(Booking.objects.filter(student=self.student, status='booked').count(), 1)
        self.assertEqual(booking.balances(self.student, 'private')['available'], 0)

    def test_failed_target_rolls_back_original_and_holds(self):
        booking.reserve(self.other, self.target.pk, uuid.uuid4())
        self.client.force_login(self.student.user)
        response = self.move()
        self.assertEqual(response.status_code, 409, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'booked')
        self.assertEqual(Booking.objects.count(), 2)

    def test_student_twelve_hour_boundary_and_coach_override(self):
        self.client.force_login(self.student.user)
        with patch('django.utils.timezone.now', return_value=self.source.start - timedelta(hours=12) + timedelta(seconds=1)):
            self.assertEqual(self.move().status_code, 409)
            self.client.force_login(self.coach)
            self.assertEqual(self.move(role='coach').status_code, 200)

    def test_foreign_booking_and_different_kind_rejected(self):
        self.client.force_login(self.other.user)
        self.assertEqual(self.move().status_code, 404)
        self.client.force_login(self.student.user)
        self.assertEqual(self.move(target=make_session(38, kind='group', capacity=2)).status_code, 409)

    def test_expired_credit_rejects_reschedule_without_losing_source(self):
        self.student.credits.update(expires_on=timezone.localdate()-timedelta(days=1))
        self.client.force_login(self.student.user)
        self.assertEqual(self.move().status_code, 409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'booked')

    def batch(self, items=None, key=None):
        return self.post('coach/lessons/batch/', {'kind':'private','occurred_on':timezone.localdate().isoformat(),
            'operation_key':str(key or uuid.uuid4()),'items':items or self.items})

    def prepare_batch(self):
        self.client.force_login(self.coach)
        booking.cancel(self.item.pk, self.coach)
        self.items = [{'student_id':s.pk,'operation_key':str(uuid.uuid4()),'note':'批量记录','exercises':[]} for s in (self.student,self.other)]

    def test_batch_failure_is_all_or_nothing(self):
        self.prepare_batch()
        self.other.credits.update(expires_on=timezone.localdate()-timedelta(days=1))
        response = self.batch()
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(DirectLesson.objects.count(), 0)
        self.assertEqual(CreditEntry.objects.filter(entry_type='consume').count(), 0)

    def test_batch_item_idempotency_and_changed_batch_key_rejected(self):
        self.prepare_batch()
        key = uuid.uuid4()
        first = self.batch(key=key)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(len(first.json()['data']['items']), 2)
        self.assertEqual(self.batch(key=key).json(), first.json())
        self.assertEqual(self.batch().status_code, 200)
        self.assertEqual(DirectLesson.objects.count(), 2)
        self.assertEqual(CreditEntry.objects.filter(entry_type='consume').count(), 2)
        self.items[0]['note'] = '不同意图'
        self.assertEqual(self.batch(key=key).status_code, 409)

    def test_batch_validation_future_duplicate_and_foreign_role(self):
        self.prepare_batch()
        self.assertEqual(self.batch(items=[self.items[0],self.items[0]]).status_code, 400)
        self.client.force_login(self.student.user)
        self.assertEqual(self.batch().status_code, 403)
