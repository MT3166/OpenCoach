from uuid import uuid5, NAMESPACE_URL
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .booking import operation_uuid, reserve
from .errors import DomainError
from .models import Session, Waitlist


def join(student, session_id, operation_key):
    key = operation_uuid(operation_key)
    with transaction.atomic():
        old = Waitlist.objects.filter(operation_key=key).first()
        if old:
            if old.student_id != student.pk or old.session_id != session_id:
                raise DomainError('操作标识已用于其他候补')
            return old
        session = get_object_or_404(Session, pk=session_id)
        if session.cancelled or session.start <= timezone.now():
            raise DomainError('这节课已开始或已取消')
        active = session.bookings.exclude(status='cancelled')
        if active.filter(student=student).exists():
            raise DomainError('你已正式预约，无需候补')
        if active.count() < session.capacity:
            raise DomainError('课程尚有名额，请直接预约')
        if Waitlist.objects.filter(student=student, session=session, status='waiting').exists():
            raise DomainError('你已在这节课的候补队列中')
        return Waitlist.objects.create(student=student, session=session, operation_key=key)


def leave(pk, student):
    with transaction.atomic():
        item = get_object_or_404(Waitlist, pk=pk, student=student)
        if item.status == 'promoted':
            raise DomainError('候补已转为预约，请在我的预约中取消或改期')
        if item.status == 'waiting':
            item.status = 'cancelled'
            item.save(update_fields=['status'])
        return item


def promote(session_id):
    """Called inside the releasing transaction; also safe as a standalone retry."""
    with transaction.atomic():
        session = get_object_or_404(Session, pk=session_id)
        if session.cancelled or session.start <= timezone.now():
            return []
        promoted = []
        for item in session.waitlist.filter(status='waiting').select_related('student__user').order_by('created_at','id'):
            if session.bookings.exclude(status='cancelled').count() >= session.capacity:
                break
            if not item.student.user_id or not item.student.user.is_active:
                continue
            try:
                key = uuid5(NAMESPACE_URL, f'opencoach.waitlist:{item.pk}:{item.operation_key}')
                result = reserve(item.student, session.pk, key)
            except DomainError:
                continue
            item.status, item.booking, item.promoted_at = 'promoted', result, timezone.now()
            item.save(update_fields=['status','booking','promoted_at'])
            promoted.append(item)
        return promoted
