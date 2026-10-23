import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from coaching.errors import DomainError
from coaching.models import Booking, Submission, TrainingPlan, TrainingRecord
from coaching.training import validate_exercises, save_record, create_plan, save_submission, review_submission
from .helpers import make_student, make_session

class TrainingTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create(username='coach', is_staff=True)
        self.student = make_student('xiaoyu')
        self.other = make_student('other')
        self.exercises = [{'name': '高脚杯深蹲', 'sets': 3, 'reps': 12, 'weight': '8', 'duration': None}]
        self.plan = TrainingPlan.objects.create(student=self.student, title='下肢稳定训练',
            due_date=timezone.localdate() + timedelta(days=1), exercises=self.exercises)
        self.booking = Booking.objects.create(student=self.student, session=make_session(offset=-2),
            status=Booking.Status.COMPLETED, operation_key=uuid.uuid4())

    def test_submission_persists_actual_training(self):
        save_submission(self.plan.id, self.student.user, self.exercises, '最后一组稍吃力', submit=True)
        self.assertTrue(Submission.objects.filter(plan=self.plan, submitted_at__isnull=False).exists())

    def test_other_student_cannot_submit(self):
        with self.assertRaises(Http404):
            save_submission(self.plan.id, self.other.user, self.exercises, '', submit=True)

    def test_student_cannot_write_class_record(self):
        with self.assertRaises(PermissionDenied):
            save_record(self.booking.id, self.student.user, self.exercises, '')

    def test_class_record_is_bound_to_booking(self):
        save_record(self.booking.id, self.coach, self.exercises, '动作控制有进步')
        self.assertTrue(TrainingRecord.objects.filter(booking=self.booking).exists())

    def test_submitted_training_cannot_be_edited(self):
        Submission.objects.create(plan=self.plan, exercises=self.exercises, submitted_at=timezone.now())
        with self.assertRaises(DomainError):
            save_submission(self.plan.id, self.student.user, self.exercises, '改写', submit=True)

    def test_teacher_feedback_is_visible_on_submission(self):
        submission = Submission.objects.create(plan=self.plan, exercises=self.exercises, submitted_at=timezone.now())
        review_submission(submission.id, self.coach, '下一次下降放慢，保持膝盖方向稳定。')
        submission.refresh_from_db()
        self.assertEqual(submission.feedback, '下一次下降放慢，保持膝盖方向稳定。')

    def test_student_cannot_review_submission(self):
        submission = Submission.objects.create(plan=self.plan, exercises=self.exercises, submitted_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            review_submission(submission.id, self.student.user, '自评冒充教练')

    def test_zero_sets_rejected(self):
        with self.assertRaises(DomainError):
            validate_exercises([{'name': '深蹲', 'sets': 0}])

    def test_nonfinite_weight_rejected(self):
        with self.assertRaises(DomainError):
            validate_exercises([{'name': '深蹲', 'weight': 'NaN'}])

    def test_zero_weight_is_preserved(self):
        rows = validate_exercises([{'name': '自重深蹲', 'weight': '0', 'reps': '12'}])
        self.assertEqual(rows[0]['weight'], '0')
        self.assertEqual(rows[0]['reps'], 12)

    def test_teacher_can_create_plan(self):
        result = create_plan(self.student, self.coach, '每日核心', timezone.localdate(),
                             self.exercises, '保持自然呼吸')
        self.assertIsNotNone(result)

    def test_student_cannot_create_plan(self):
        with self.assertRaises(PermissionDenied):
            create_plan(self.student, self.student.user, '冒充', timezone.localdate(), self.exercises, '')

    def test_extreme_fractional_weight_is_rejected_before_expansion(self):
        for weight in ['1e-1000000', '1e-1000000000', '0.001']:
            with self.subTest(weight=weight), self.assertRaises(DomainError):
                validate_exercises([{'name': '深蹲', 'weight': weight}])

    def test_quarter_kilogram_weight_is_preserved(self):
        self.assertEqual(validate_exercises([{'name': '划船', 'weight': '6.2500'}])[0]['weight'], '6.25')
