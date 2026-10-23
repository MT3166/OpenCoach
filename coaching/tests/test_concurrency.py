import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from coaching.booking import reserve, finish, add_credit, balances
from coaching.errors import DomainError
from coaching.models import Booking, CreditEntry, Kind
from .helpers import make_student, make_session

class ConcurrencyTests(TransactionTestCase):
    def race(self, calls, final_count=1):
        barrier = Barrier(2)
        def run(args):
            close_old_connections()
            try:
                connection.ensure_connection()
                barrier.wait(timeout=10)
                try:
                    return reserve(*args) is not None
                except DomainError:
                    return False
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, calls))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(Booking.objects.count(), final_count)

    def test_last_seat_is_atomic(self):
        first = make_student('first')
        second = make_student('second')
        session = make_session()
        self.race([(first, session.id, uuid.uuid4()), (second, session.id, uuid.uuid4())])

    def test_last_credit_is_atomic(self):
        student = make_student('one-credit', credits=1)
        a = make_session(offset=30)
        b = make_session(offset=32)
        self.race([(student, a.id, uuid.uuid4()), (student, b.id, uuid.uuid4())])

    def duplicate_race(self, action):
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                connection.ensure_connection()
                barrier.wait(timeout=10)
                return action().pk
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(results[0], results[1])

    def test_duplicate_purchase_is_atomic(self):
        student = make_student('purchase', credits=0)
        key = uuid.uuid4()
        self.duplicate_race(lambda: add_credit(student, Kind.PRIVATE, 3, key))
        self.assertEqual(CreditEntry.objects.count(), 1)
        self.assertEqual(balances(student, Kind.PRIVATE)['remaining'], 3)

    def test_duplicate_completion_is_atomic(self):
        student = make_student('completion')
        coach = get_user_model().objects.create(username='coach', is_staff=True)
        item = Booking.objects.create(student=student, session=make_session(offset=-2), operation_key=uuid.uuid4())
        self.duplicate_race(lambda: finish(item.id, coach, 'completed'))
        self.assertEqual(CreditEntry.objects.filter(booking=item).count(), 1)
        self.assertEqual(balances(student, Kind.PRIVATE)['remaining'], 1)

    def test_duplicate_reservation_is_atomic(self):
        student = make_student('reservation')
        session = make_session()
        key = uuid.uuid4()
        self.duplicate_race(lambda: reserve(student, session.id, key))
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(balances(student, Kind.PRIVATE)['reserved'], 1)

    def test_last_group_seat_is_atomic(self):
        session = make_session(kind=Kind.GROUP, capacity=2)
        first = make_student('group-first', kind=Kind.GROUP)
        Booking.objects.create(student=first, session=session, operation_key=uuid.uuid4())
        second = make_student('group-second', kind=Kind.GROUP)
        third = make_student('group-third', kind=Kind.GROUP)
        self.race([(second, session.id, uuid.uuid4()), (third, session.id, uuid.uuid4())], final_count=2)
