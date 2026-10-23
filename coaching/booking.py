from datetime import date, timedelta
from uuid import UUID
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .errors import DomainError
from .models import Booking, CreditEntry, Kind, Session
from .credits import wallet, purchase_for_charge

def require_coach(actor):
    if not actor.is_authenticated or not actor.is_staff or not actor.is_active:
        raise PermissionDenied

def operation_uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise DomainError('操作标识无效，请刷新页面重试') from exc

def create_session(title, kind, start, end, location, capacity):
    if kind not in Kind.values or end <= start or start <= timezone.now():
        raise DomainError('请选择有效的未来上课时间')
    if not title.strip() or not location.strip() or len(title) > 80 or len(location) > 120:
        raise DomainError('请填写课程名称和上课地点')
    if (kind == Kind.PRIVATE and capacity != 1) or (kind == Kind.GROUP and capacity < 2):
        raise DomainError('私教限 1 人，小班至少设置 2 个名额')
    with transaction.atomic():
        if Session.objects.filter(cancelled=False, start__lt=end, end__gt=start).exists():
            raise DomainError('这段时间已有课程，请调整排课时间')
        return Session.objects.create(title=title.strip(), kind=kind, start=start, end=end,
                                      location=location.strip(), capacity=capacity)

def add_credit(student, kind, units, operation_key, expires_on=None):
    key = operation_uuid(operation_key)
    if kind not in Kind.values or isinstance(units, bool) or not isinstance(units, int) or units <= 0:
        raise DomainError('购买课时必须是正整数')
    if expires_on is not None and type(expires_on) is not date:
        raise DomainError('到期日须为有效日期')
    with transaction.atomic():
        old = CreditEntry.objects.filter(operation_key=key).first()
        if old:
            if (old.student_id, old.kind, old.units, old.expires_on) != (student.id, kind, units, expires_on):
                raise DomainError('操作标识已用于其他课包录入')
            return old
        return CreditEntry.objects.create(student=student, kind=kind, entry_type='purchase',
                                         units=units, operation_key=key, expires_on=expires_on)

def balances(student, kind):
    current = wallet(student, kind)
    # Keep the existing Python helper's shape; the API exposes expiry details.
    return {key: current[key] for key in ('remaining', 'reserved', 'available')}

def reserve(student, session_id, operation_key):
    key = operation_uuid(operation_key)
    with transaction.atomic():
        old = Booking.objects.filter(operation_key=key).first()
        if old:
            if old.student_id != student.id or old.session_id != session_id:
                raise DomainError('操作标识已用于其他预约')
            return old
        session = get_object_or_404(Session, pk=session_id)
        if session.cancelled or session.start <= timezone.now():
            raise DomainError('这节课程已开始或已取消')
        existing = Booking.objects.exclude(status=Booking.Status.CANCELLED)
        if existing.filter(student=student, session=session).exists():
            raise DomainError('你已经预约了这节课')
        if existing.filter(session=session).count() >= session.capacity:
            raise DomainError('课程已满员，请选择其他时段')
        if existing.filter(student=student, session__start__lt=session.end,
                           session__end__gt=session.start).exists():
            raise DomainError('与你已预约的课程时间冲突')
        if balances(student, session.kind)['available'] < 1:
            raise DomainError('可约课时不足，请联系教练录入课包')
        return Booking.objects.create(student=student, session=session, operation_key=key)

def cancel(booking_id, actor):
    with transaction.atomic():
        item = get_object_or_404(Booking.objects.select_related('student', 'session'), pk=booking_id)
        if not actor.is_authenticated or (not actor.is_staff and item.student.user_id != actor.id):
            raise Http404
        if item.status == Booking.Status.CANCELLED:
            return item
        if item.status != Booking.Status.BOOKED:
            raise DomainError('这笔预约已经处理，不能取消')
        if not actor.is_staff and timezone.now() > item.session.start - timedelta(hours=12):
            raise DomainError('距开课不足 12 小时，请联系教练处理')
        item.status = Booking.Status.CANCELLED
        item.save(update_fields=['status'])
        from .waitlist import promote
        promote(item.session_id)
        return item

def cancel_session(session_id, actor):
    require_coach(actor)
    with transaction.atomic():
        session = get_object_or_404(Session, pk=session_id)
        if session.cancelled:
            return session
        if session.bookings.filter(status__in=[Booking.Status.COMPLETED, Booking.Status.NO_SHOW_CHARGED]).exists():
            raise DomainError('课程已有消课记录，请逐人处理剩余预约')
        session.bookings.filter(status=Booking.Status.BOOKED).update(status=Booking.Status.CANCELLED)
        session.cancelled = True
        session.save(update_fields=['cancelled'])
        session.waitlist.filter(status='waiting').update(status='cancelled')
        return session

def reschedule(booking_id, actor, session_id, operation_key):
    key = operation_uuid(operation_key)
    with transaction.atomic():
        item = get_object_or_404(Booking.objects.select_related('student', 'session'), pk=booking_id)
        if not actor.is_authenticated or not actor.is_active or (not actor.is_staff and item.student.user_id != actor.id):
            raise Http404
        old = Booking.objects.filter(operation_key=key).first()
        if old:
            if old.rescheduled_from_id != item.pk or old.session_id != session_id:
                raise DomainError('操作标识已用于其他改期')
            return old
        if item.status != Booking.Status.BOOKED or item.session.cancelled:
            raise DomainError('仅可改期未处理的有效预约')
        if not actor.is_staff and timezone.now() > item.session.start - timedelta(hours=12):
            raise DomainError('距原课开课不足12小时，请联系教练改期')
        target = get_object_or_404(Session, pk=session_id)
        if target.pk == item.session_id or target.kind != item.session.kind:
            raise DomainError('请选择同课包类型的其他课程')
        item.status = Booking.Status.CANCELLED
        item.save(update_fields=['status'])
        moved = reserve(item.student, session_id, key)
        moved.rescheduled_from = item
        moved.save(update_fields=['rescheduled_from'])
        from .waitlist import promote
        promote(item.session_id)
        return moved

def finish(booking_id, actor, outcome):
    require_coach(actor)
    allowed = [Booking.Status.COMPLETED, Booking.Status.NO_SHOW_CHARGED, Booking.Status.NO_SHOW_WAIVED]
    if outcome not in allowed:
        raise DomainError('请选择有效的出勤处理方式')
    with transaction.atomic():
        item = get_object_or_404(Booking.objects.select_related('student', 'session'), pk=booking_id)
        if item.status == outcome:
            return item
        if item.status != Booking.Status.BOOKED or item.session.cancelled:
            raise DomainError('这笔预约已经处理')
        if item.session.start > timezone.now():
            raise DomainError('课程尚未开始，暂不能确认完课或缺席')
        if outcome != Booking.Status.NO_SHOW_WAIVED:
            purchase = purchase_for_charge(item.student, item.session.kind, item.pk)
            CreditEntry.objects.create(student=item.student, kind=item.session.kind,
                                      entry_type='consume', units=1, booking=item, purchase=purchase)
        item.status = outcome
        item.save(update_fields=['status'])
        return item
