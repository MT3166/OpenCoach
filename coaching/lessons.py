from datetime import date
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .booking import require_coach, operation_uuid
from .errors import DomainError
from .models import CreditEntry, DirectLesson, Kind, LessonBatch, Student
from .training import clean_note, validate_exercises
from .credits import purchase_for_charge

def optional_exercises(items):
    return [] if items == [] else validate_exercises(items)

def record_direct_lesson(student, actor, kind, occurred_on, note, operation_key, exercises=None):
    require_coach(actor)
    key = operation_uuid(operation_key)
    if kind not in Kind.values or type(occurred_on) is not date or occurred_on > timezone.localdate():
        raise DomainError('请选择已上课的日期与课包类型')
    rows = optional_exercises([] if exercises is None else exercises)
    note = clean_note(note)
    with transaction.atomic():
        old = DirectLesson.objects.filter(operation_key=key).first()
        if old:
            if (old.student_id,old.kind,old.occurred_on) != (student.id,kind,occurred_on):
                raise DomainError('操作标识已用于另一节课，请核对记录')
            return old
        purchase = purchase_for_charge(student, kind)
        lesson = DirectLesson.objects.create(student=student,kind=kind,occurred_on=occurred_on,
            exercises=rows,note=note,operation_key=key,created_by=actor)
        CreditEntry.objects.create(student=student,kind=kind,entry_type='consume',units=1,direct_lesson=lesson,purchase=purchase)
        return lesson

def update_lesson_note(lesson_id, actor, note=None, exercises=None):
    require_coach(actor)
    note = clean_note(note) if note is not None else None
    rows = optional_exercises(exercises) if exercises is not None else None
    with transaction.atomic():
        lesson = get_object_or_404(DirectLesson,pk=lesson_id)
        if note is not None:
            lesson.note = note
        if rows is not None:
            lesson.exercises = rows
        lesson.save(update_fields=['note','exercises','updated_at'])
        return lesson

def record_batch(actor, kind, occurred_on, operation_key, items):
    require_coach(actor)
    key = operation_uuid(operation_key)
    payload = {'kind':kind, 'occurred_on':occurred_on.isoformat(), 'items':[
        {**row, 'operation_key':str(row['operation_key'])} for row in items]}
    with transaction.atomic():
        old = LessonBatch.objects.filter(operation_key=key).first()
        if old:
            if old.payload != payload:
                raise DomainError('批次操作标识已用于其他记课内容')
            indexed = DirectLesson.objects.in_bulk(old.lesson_ids)
            return [indexed[pk] for pk in old.lesson_ids]
        results = []
        for row in items:
            student = get_object_or_404(Student, pk=row['student_id'])
            results.append(record_direct_lesson(student, actor, kind, occurred_on,
                row.get('note', ''), row['operation_key'], row.get('exercises', [])))
        LessonBatch.objects.create(operation_key=key, payload=payload, lesson_ids=[item.pk for item in results])
        return results
