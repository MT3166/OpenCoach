from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from .credits import lots
from .models import Booking, CreditEntry, DirectLesson, Waitlist


def month_bounds(month):
    start = datetime.strptime(month, '%Y-%m').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    if start.strftime('%Y-%m') != month:
        raise ValueError('invalid month')
    if start.year == 1 and start.month == 1:
        raise ValueError('month before supported reporting range')
    end = start.replace(year=start.year+1, month=1) if start.month == 12 else start.replace(month=start.month+1)
    return start, end


@transaction.atomic
def monthly(month):
    start, end = month_bounds(month)
    booked = Booking.objects.filter(session__start__gte=start, session__start__lt=end)
    counts = booked.aggregate(
        scheduled_attended=Count('id', filter=Q(status='completed')),
        scheduled_missed=Count('id', filter=Q(status__in=['no_show_charged','no_show_waived'])),
        scheduled_cancelled=Count('id', filter=Q(status='cancelled')),
        pending=Count('id', filter=Q(status='booked',session__start__lte=timezone.now(),session__cancelled=False)))
    handled = booked.filter(session__cancelled=False)
    attended = handled.filter(status='completed').count()
    missed = handled.filter(status__in=['no_show_charged','no_show_waived']).count()
    first_expiry, last_expiry = start.date()-timedelta(days=1), end.date()-timedelta(days=1)
    expired = CreditEntry.objects.filter(entry_type='purchase', expires_on__gte=first_expiry,
        expires_on__lt=min(last_expiry, timezone.localdate()))
    candidates = set(expired.values_list('student_id','kind'))
    credit_expired = 0
    for student_id, kind in candidates:
        for lot in lots(student_id, kind):
            expiry = lot['entry'].expires_on
            if expiry and first_expiry <= expiry < last_expiry and expiry < timezone.localdate():
                credit_expired += lot['units']
    return {'month':month, **counts,
        'direct_attended':DirectLesson.objects.filter(occurred_on__gte=start.date(),occurred_on__lt=end.date()).count(),
        'waitlist_promoted':Waitlist.objects.filter(promoted_at__gte=start,promoted_at__lt=end).count(),
        'credit_expired':credit_expired,
        'scheduled_rate':round(attended/(attended+missed)*100,1) if attended+missed else 0,
        'scheduled_denominator':attended+missed}
