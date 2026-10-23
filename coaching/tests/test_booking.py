import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from coaching import booking
from coaching.errors import DomainError
from coaching.models import Booking, CreditEntry, Kind
from .helpers import make_student, make_session

class BookingTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='coach', is_staff=True)
        self.student = make_student('xiaoyu')
        self.session = make_session()

    def booked(self, student=None, session=None):
        return Booking.objects.create(student=student or self.student, session=session or self.session,
                                      operation_key=uuid.uuid4())

    def test_reservation_holds_credit_without_consuming(self):
        result = booking.reserve(self.student, self.session.id, uuid.uuid4())
        self.assertIsNotNone(result)
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE),
                         {'remaining': 2, 'reserved': 1, 'available': 1})

    def test_last_seat_cannot_be_taken_twice(self):
        self.booked()
        second = make_student('achen')
        with self.assertRaises(DomainError):
            booking.reserve(second, self.session.id, uuid.uuid4())

    def test_no_credit_rejects_booking(self):
        no_credit = make_student('empty', credits=0)
        with self.assertRaises(DomainError):
            booking.reserve(no_credit, self.session.id, uuid.uuid4())

    def test_duplicate_operation_is_same_booking(self):
        key = uuid.uuid4()
        booking.reserve(self.student, self.session.id, key)
        booking.reserve(self.student, self.session.id, key)
        self.assertEqual(Booking.objects.count(), 1)

    def test_duplicate_enrollment_rejected(self):
        self.booked()
        with self.assertRaises(DomainError):
            booking.reserve(self.student, self.session.id, uuid.uuid4())

    def test_student_time_conflict_rejected(self):
        self.booked()
        overlap = make_session(offset=30.5)
        with self.assertRaises(DomainError):
            booking.reserve(self.student, overlap.id, uuid.uuid4())

    def test_coach_cannot_publish_overlapping_session(self):
        with self.assertRaises(DomainError):
            booking.create_session('重叠课程', Kind.PRIVATE, self.session.start,
                self.session.end, '训练室', 1)

    def test_adjacent_session_is_allowed(self):
        result = booking.create_session('下一节', Kind.PRIVATE, self.session.end,
            self.session.end + timedelta(hours=1), '训练室', 1)
        self.assertIsNotNone(result)

    def test_cancellation_exactly_twelve_hours_releases_credit(self):
        item = self.booked()
        with patch('coaching.booking.timezone.now', return_value=self.session.start - timedelta(hours=12)):
            booking.cancel(item.id, self.student.user)
        item.refresh_from_db()
        self.assertEqual(item.status, Booking.Status.CANCELLED)
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE)['available'], 2)

    def test_late_student_cancellation_rejected(self):
        item = self.booked()
        with patch('coaching.booking.timezone.now', return_value=self.session.start - timedelta(hours=12) + timedelta(seconds=1)):
            with self.assertRaises(DomainError):
                booking.cancel(item.id, self.student.user)

    def test_old_cancellation_retry_does_not_cancel_new_booking(self):
        old = self.booked()
        booking.cancel(old.id, self.student.user)
        new = booking.reserve(self.student, self.session.id, uuid.uuid4())
        self.assertIsNotNone(new)
        booking.cancel(old.id, self.student.user)
        new.refresh_from_db()
        self.assertEqual(new.status, Booking.Status.BOOKED)
        self.assertEqual(Booking.objects.count(), 2)

    def test_other_student_cannot_cancel(self):
        item = self.booked()
        other = make_student('other')
        with self.assertRaises(Http404):
            booking.cancel(item.id, other.user)

    def test_completion_before_start_rejected(self):
        item = self.booked()
        with self.assertRaises(DomainError):
            booking.finish(item.id, self.coach, 'completed')

    def test_duplicate_completion_charges_once(self):
        item = self.booked(session=make_session(offset=-2))
        booking.finish(item.id, self.coach, 'completed')
        booking.finish(item.id, self.coach, 'completed')
        self.assertEqual(CreditEntry.objects.filter(booking=item).count(), 1)
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE),
                         {'remaining': 1, 'reserved': 0, 'available': 1})

    def test_missing_student_can_be_waived(self):
        item = self.booked(session=make_session(offset=-2))
        booking.finish(item.id, self.coach, 'no_show_waived')
        item.refresh_from_db()
        self.assertEqual(item.status, Booking.Status.NO_SHOW_WAIVED)
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE)['available'], 2)

    def test_missing_student_can_be_charged(self):
        item = self.booked(session=make_session(offset=-2))
        booking.finish(item.id, self.coach, 'no_show_charged')
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE)['remaining'], 1)

    def test_credit_retry_does_not_add_twice(self):
        key = uuid.uuid4()
        booking.add_credit(self.student, Kind.PRIVATE, 3, key)
        booking.add_credit(self.student, Kind.PRIVATE, 3, key)
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE)['remaining'], 5)

    def test_group_completion_is_per_student(self):
        group = make_session(offset=-2, kind=Kind.GROUP, capacity=4)
        a = make_student('group-a', kind=Kind.GROUP)
        b = make_student('group-b', kind=Kind.GROUP)
        first = self.booked(student=a, session=group)
        second = self.booked(student=b, session=group)
        booking.finish(first.id, self.coach, 'completed')
        second.refresh_from_db()
        self.assertEqual(second.status, Booking.Status.BOOKED)
        self.assertEqual(booking.balances(b, Kind.GROUP),
                         {'remaining': 2, 'reserved': 1, 'available': 1})

    def test_course_cancellation_releases_all_holds(self):
        item = self.booked()
        booking.cancel_session(self.session.id, self.coach)
        item.refresh_from_db()
        self.assertEqual(item.status, Booking.Status.CANCELLED)
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE)['available'], 2)

    def test_coach_can_cancel_started_course_without_consumption(self):
        course = make_session(offset=-2)
        item = self.booked(session=course)
        booking.cancel_session(course.id, self.coach)
        item.refresh_from_db()
        self.assertEqual(item.status, Booking.Status.CANCELLED)
        self.assertFalse(CreditEntry.objects.filter(booking=item).exists())
        self.assertEqual(booking.balances(self.student, Kind.PRIVATE)['available'], 2)

    def test_partially_consumed_group_cannot_be_cancelled_whole(self):
        course = make_session(offset=-2, kind=Kind.GROUP, capacity=4)
        first = make_student('first-group', kind=Kind.GROUP)
        second = make_student('second-group', kind=Kind.GROUP)
        done = self.booked(student=first, session=course)
        waiting = self.booked(student=second, session=course)
        booking.finish(done.id, self.coach, 'completed')
        with self.assertRaises(DomainError):
            booking.cancel_session(course.id, self.coach)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Booking.Status.BOOKED)
        self.assertEqual(CreditEntry.objects.filter(booking=done).count(), 1)
