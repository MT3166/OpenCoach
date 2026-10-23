import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from coaching import lessons, booking
from coaching.errors import DomainError
from coaching.models import DirectLesson, CreditEntry
from .helpers import make_student, make_session

class DirectLessonServiceTests(TestCase):
    def setUp(self):
        self.coach=get_user_model().objects.create_user('service-coach',is_staff=True)
        self.student=make_student('service-student',credits=2)

    def test_consumption_requires_one_real_source(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CreditEntry.objects.create(student=self.student,kind='private',entry_type='consume',units=1)

    def test_direct_charge_has_same_student_and_kind(self):
        item=lessons.record_direct_lesson(self.student,self.coach,'private',timezone.localdate(),'',uuid.uuid4())
        self.assertEqual((item.charge.student_id,item.charge.kind,item.charge.units),(self.student.id,'private',1))
        self.assertIsNone(item.charge.booking_id)

    def test_second_kind_does_not_change_private_wallet(self):
        booking.add_credit(self.student,'group',3,uuid.uuid4())
        lessons.record_direct_lesson(self.student,self.coach,'group',timezone.localdate(),'小班课',uuid.uuid4())
        self.assertEqual(booking.balances(self.student,'private')['remaining'],2)
        self.assertEqual(booking.balances(self.student,'group')['remaining'],2)

class DirectLessonConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.coach=get_user_model().objects.create_user('race-coach',is_staff=True)
        self.student=make_student('race-student',credits=1)

    def race(self, actions):
        gate=Barrier(2)
        def execute(action):
            close_old_connections()
            try:
                connection.ensure_connection()
                gate.wait(timeout=10)
                try:
                    return action().pk
                except DomainError:
                    return None
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(execute,actions))

    def direct(self,key):
        return lambda:lessons.record_direct_lesson(self.student,self.coach,'private',timezone.localdate(),'',key)

    def test_last_credit_is_only_consumed_once(self):
        result=self.race([self.direct(uuid.uuid4()),self.direct(uuid.uuid4())])
        self.assertEqual(sum(item is not None for item in result),1)
        self.assertEqual(DirectLesson.objects.count(),1)
        self.assertEqual(CreditEntry.objects.filter(entry_type='consume').count(),1)
        self.assertEqual(booking.balances(self.student,'private')['available'],0)

    def test_duplicate_operation_returns_same_record(self):
        key=uuid.uuid4()
        result=self.race([self.direct(key),self.direct(key)])
        self.assertIsNotNone(result[0])
        self.assertEqual(result[0],result[1])
        self.assertEqual(DirectLesson.objects.count(),1)

    def test_direct_record_and_reservation_compete_for_same_credit(self):
        session=make_session()
        result=self.race([self.direct(uuid.uuid4()),lambda:booking.reserve(self.student,session.id,uuid.uuid4())])
        self.assertEqual(sum(item is not None for item in result),1)
        wallet=booking.balances(self.student,'private')
        self.assertEqual(wallet['available'],0)
        self.assertIn((wallet['remaining'],wallet['reserved']),[(0,0),(1,1)])
