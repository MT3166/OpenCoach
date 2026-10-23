from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .booking import require_coach
from .errors import DomainError
from .models import Booking, Submission, TrainingPlan, TrainingRecord

def validate_exercises(items):
    if not isinstance(items, list) or not items or len(items) > 50:
        raise DomainError('请填写 1–50 个训练动作')
    result = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str):
            raise DomainError('训练动作格式无效')
        name = item['name'].strip()
        if not name or len(name) > 80:
            raise DomainError('请填写动作名称，最多 80 个字符')
        row = {'name': name}
        for key in ['sets', 'reps', 'weight', 'duration']:
            raw = item.get(key)
            if raw is None or raw == '':
                row[key] = None
                continue
            try:
                if isinstance(raw, bool) or len(str(raw)) > 32:
                    raise ValueError
                value = Decimal(str(raw))
                if not value.is_finite() or value > 1000000 or value < 0:
                    raise ValueError
                if key != 'weight' and (value == 0 or value != value.to_integral_value()):
                    raise ValueError
                if key == 'weight' and value:
                    if value.adjusted() < -2 or value.normalize().as_tuple().exponent < -2:
                        raise ValueError
                row[key] = format(value.normalize(), 'f') if key == 'weight' else int(value)
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise DomainError('组数、次数、时长须为正整数；重量须为非负数，最多两位小数') from exc
        result.append(row)
    return result

def clean_note(note):
    if not isinstance(note, str) or len(note) > 4000:
        raise DomainError('文字说明最多 4000 个字符')
    return note.strip()

def save_record(booking_id, actor, exercises, note):
    require_coach(actor)
    rows, note = ([] if exercises == [] else validate_exercises(exercises)), clean_note(note)
    with transaction.atomic():
        booking = get_object_or_404(Booking, pk=booking_id)
        if booking.status != Booking.Status.COMPLETED:
            raise DomainError('请先确认学员已完成课程')
        record, _ = TrainingRecord.objects.update_or_create(booking=booking,
            defaults={'exercises': rows, 'note': note})
        return record

def create_plan(student, actor, title, due_date, exercises, note, booking=None):
    require_coach(actor)
    title, note = title.strip(), clean_note(note)
    if not title or len(title) > 80 or not isinstance(due_date, date):
        raise DomainError('请填写计划名称和目标日期')
    if booking and booking.student_id != student.id:
        raise DomainError('计划和课程必须属于同一学员')
    return TrainingPlan.objects.create(student=student, title=title, due_date=due_date,
        exercises=validate_exercises(exercises), note=note, booking=booking)

def save_submission(plan_id, actor, exercises, note, submit=False):
    if not actor.is_authenticated or actor.is_staff:
        raise PermissionDenied
    rows, note = validate_exercises(exercises), clean_note(note)
    with transaction.atomic():
        plan = get_object_or_404(TrainingPlan, pk=plan_id, student__user=actor)
        if len(rows) != len(plan.exercises):
            raise DomainError('请按计划填写每个动作的完成情况')
        for index, row in enumerate(rows):
            row['name'] = plan.exercises[index]['name']
        if submit and not note and not any(row[key] is not None for row in rows for key in ['sets', 'reps', 'weight', 'duration']):
            raise DomainError('请填写实际数据或训练感受再提交')
        submission, _ = Submission.objects.get_or_create(plan=plan)
        if submission.submitted_at:
            if submit and submission.exercises == rows and submission.note == note:
                return submission
            raise DomainError('已提交的训练记录不可修改')
        submission.exercises, submission.note = rows, note
        if submit:
            submission.submitted_at = timezone.now()
        submission.save()
        return submission

def review_submission(submission_id, actor, feedback):
    require_coach(actor)
    feedback = clean_note(feedback)
    if not feedback:
        raise DomainError('请填写给学员的反馈')
    with transaction.atomic():
        submission = get_object_or_404(Submission, pk=submission_id)
        if not submission.submitted_at:
            raise DomainError('学员还未正式提交训练')
        submission.feedback = feedback
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['feedback', 'reviewed_at', 'updated_at'])
        return submission
