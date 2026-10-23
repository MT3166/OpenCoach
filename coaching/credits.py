"""Purchase lots and effective holds; all writes are made by atomic domain services."""
from datetime import date, timedelta
from django.utils import timezone
from .errors import DomainError
from .models import Booking, CreditEntry


def lots(student, kind):
    entries = list(CreditEntry.objects.filter(student=student, kind=kind).order_by('created_at', 'id'))
    purchases = {item.pk: {'entry': item, 'units': item.units} for item in entries if item.entry_type == 'purchase'}
    legacy = []
    for item in entries:
        if item.entry_type != 'consume':
            continue
        if item.purchase_id in purchases:
            purchases[item.purchase_id]['units'] -= item.units
        else:
            legacy.append(item)
    # Old ledgers did not carry a purchase reference. Their permanent purchases
    # retain FIFO accounting without changing any historical entry.
    for item in legacy:
        left = item.units
        for lot in purchases.values():
            used = min(left, max(0, lot['units']))
            lot['units'] -= used
            left -= used
            if not left:
                break
    return list(purchases.values())


def allocation(student, kind):
    today = timezone.localdate()
    batches = lots(student, kind)
    valid = sorted((lot for lot in batches if lot['entry'].expires_on is None or lot['entry'].expires_on >= today),
                   key=lambda lot: (lot['entry'].expires_on or date.max, lot['entry'].created_at, lot['entry'].pk))
    free = {lot['entry'].pk: max(0, lot['units']) for lot in valid}
    holds = {}
    for item in Booking.objects.filter(student=student, session__kind=kind, status='booked').order_by('created_at', 'id'):
        for lot in valid:
            pk = lot['entry'].pk
            if free[pk]:
                free[pk] -= 1
                holds[item.pk] = lot['entry']
                break
    return batches, valid, free, holds


def wallet(student, kind):
    batches, valid, free, holds = allocation(student, kind)
    today = timezone.localdate()
    remaining = sum(lot['units'] for lot in batches)
    expired = sum(lot['units'] for lot in batches if lot['entry'].expires_on and lot['entry'].expires_on < today)
    expiring = [{'expires_on':lot['entry'].expires_on.isoformat(), 'units':lot['units']}
                for lot in valid if lot['units'] > 0 and lot['entry'].expires_on and lot['entry'].expires_on <= today + timedelta(days=7)]
    return {'remaining':remaining, 'reserved':len(holds), 'expired':expired,
            'available':remaining - expired - len(holds), 'expiring':expiring}


def purchase_for_charge(student, kind, booking_id=None):
    _, valid, free, holds = allocation(student, kind)
    if booking_id is not None:
        purchase = holds.get(booking_id)
        if purchase:
            return purchase
    else:
        for lot in valid:
            if free[lot['entry'].pk] > 0:
                return lot['entry']
    raise DomainError('有效可用课时不足，请核对到期日、预约预占或录入续课')
