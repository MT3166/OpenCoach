import uuid
from datetime import timedelta, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from coaching import booking, lessons
from coaching.errors import DomainError
from coaching.models import CreditEntry
from coaching.api.serializers import wallets, credit_data
from .helpers import make_student, make_session


class CreditExpiryTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='expiry-coach', is_staff=True)
        self.student = make_student('expiry-student', credits=0)
        self.today = timezone.localdate()

    def purchase(self, units=1, day=None):
        return booking.add_credit(self.student, 'private', units, uuid.uuid4(), expires_on=day)

    def test_expired_credit_is_visible_but_cannot_book_or_consume(self):
        entry = self.purchase(3, self.today - timedelta(days=1))
        wallet = wallets(self.student)[0]
        self.assertEqual((wallet['remaining'], wallet['expired'], wallet['available']), (3, 3, 0))
        self.assertEqual(credit_data(entry)['expires_on'], (self.today - timedelta(days=1)).isoformat())
        with self.assertRaises(DomainError):
            booking.reserve(self.student, make_session().pk, uuid.uuid4())
        with self.assertRaises(DomainError):
            lessons.record_direct_lesson(self.student, self.coach, 'private', self.today - timedelta(days=2), '', uuid.uuid4())

    def test_expiry_day_can_book_and_finish_but_next_day_cannot(self):
        self.purchase(2, self.today)
        item = booking.reserve(self.student, make_session().pk, uuid.uuid4())
        with patch('django.utils.timezone.now', return_value=item.session.start):
            # The booking is in the future, after today's batch expires.
            with self.assertRaises(DomainError):
                booking.finish(item.pk, self.coach, 'completed')
        past = make_session(offset=-2)
        item.session = past
        item.save(update_fields=['session'])
        booking.finish(item.pk, self.coach, 'completed')
        self.assertEqual(wallets(self.student)[0]['remaining'], 1)

    def test_old_purchases_are_permanent_and_reservations_protected(self):
        entry = booking.add_credit(self.student, 'private', 1, uuid.uuid4())
        self.assertIsNone(credit_data(entry)['expires_on'])
        booking.reserve(self.student, make_session().pk, uuid.uuid4())
        with self.assertRaises(DomainError):
            lessons.record_direct_lesson(self.student, self.coach, 'private', self.today, '', uuid.uuid4())

    def test_earliest_expiring_is_consumed_first_and_not_reported_expired(self):
        self.purchase(2)
        expiring = self.purchase(1, self.today)
        lessons.record_direct_lesson(self.student, self.coach, 'private', self.today, '', uuid.uuid4())
        with patch('django.utils.timezone.now', return_value=datetime.combine(self.today + timedelta(days=1), datetime.min.time(), ZoneInfo('Asia/Shanghai'))):
            self.assertEqual(wallets(self.student)[0]['expired'], 0)
        self.assertEqual(CreditEntry.objects.get(entry_type='consume').purchase_id, expiring.pk)

    def test_shanghai_midnight_and_expiring_reminder(self):
        self.purchase(2, self.today)
        self.assertEqual(wallets(self.student)[0]['expiring'][0]['units'], 2)
        midnight = datetime.combine(self.today + timedelta(days=1), datetime.min.time(), ZoneInfo('Asia/Shanghai'))
        with patch('django.utils.timezone.now', return_value=midnight - timedelta(seconds=1)):
            self.assertEqual(wallets(self.student)[0]['available'], 2)
        with patch('django.utils.timezone.now', return_value=midnight):
            self.assertEqual(wallets(self.student)[0]['expired'], 2)

    def test_expiry_changes_cannot_reuse_purchase_key(self):
        key = uuid.uuid4()
        booking.add_credit(self.student, 'private', 1, key, expires_on=self.today)
        with self.assertRaises(DomainError):
            booking.add_credit(self.student, 'private', 1, key)

    def test_credit_api_expiry_validation_and_wallet_contract(self):
        self.client.force_login(self.coach)
        url = f'/api/v1/coach/students/{self.student.pk}/credits/'
        response = self.client.post(url, {'kind':'private','units':2,'operation_key':str(uuid.uuid4()),'expires_on':self.today.isoformat()}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['data']['wallets'][0]['expired'], 0)
        response = self.client.post(url, {'kind':'private','units':2,'operation_key':str(uuid.uuid4()),'expires_on':'bad'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
