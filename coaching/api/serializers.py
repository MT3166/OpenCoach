from datetime import timedelta
from django.utils import timezone
from coaching.models import Kind
from coaching.credits import wallet

def student_data(item):
    return {'id':item.id,'name':item.name,'registered':bool(item.user_id)}

def wallets(student):
    return [{'kind':kind,'label':label,**wallet(student,kind)} for kind,label in Kind.choices]

def course_data(item):
    occupied = getattr(item,'occupied',None)
    if occupied is None:
        occupied = item.bookings.exclude(status='cancelled').count()
    return {'id':item.id,'title':item.title,'kind':item.kind,'start':item.start.isoformat(),
            'end':item.end.isoformat(),'location':item.location,'capacity':item.capacity,
            'occupied':occupied,'slots_left':item.capacity-occupied,'cancelled':item.cancelled,
            'my_booking_id':getattr(item,'my_booking_id',None),
            'my_waitlist_id':getattr(item,'my_waitlist_id',None)}

def booking_data(item, coach=False):
    data = {'id':item.id,'status':item.status,'session':course_data(item.session),
            'can_cancel':item.status=='booked' and timezone.now() <= item.session.start-timedelta(hours=12),
            'can_finish':item.status=='booked' and item.session.start <= timezone.now() and not item.session.cancelled}
    if coach:
        data['student'] = student_data(item.student)
    else:
        data['session']['my_booking_id'] = item.id
    return data

def record_data(item):
    if not item:
        return None
    return {'id':item.id,'booking_id':item.booking_id,'exercises':item.exercises,
            'note':item.note,'updated_at':item.updated_at.isoformat()}

def lesson_data(item, source):
    record = getattr(item,'record',None) if source=='booking' else item
    return {'source':source,'id':item.id,'student':student_data(item.student),
            'kind':item.session.kind if source=='booking' else item.kind,
            'occurred_on':(timezone.localdate(item.session.start) if source=='booking' else item.occurred_on).isoformat(),
            'exercises':record.exercises if record else [],'note':record.note if record else ''}

def credit_data(item):
    return {'id':item.id,'kind':item.kind,'entry_type':item.entry_type,'units':item.units,
            'booking_id':item.booking_id,'direct_lesson_id':item.direct_lesson_id,
            'created_at':item.created_at.isoformat(),
            'expires_on':item.expires_on.isoformat() if item.expires_on else None,
            'title':item.booking.session.title if item.booking_id else ('直接记课' if item.direct_lesson_id else '购买 / 续课录入')}

def submission_data(item):
    if not item:
        return None
    return {'id':item.id,'exercises':item.exercises,'note':item.note,
            'submitted_at':item.submitted_at.isoformat() if item.submitted_at else None,
            'feedback':item.feedback,'reviewed_at':item.reviewed_at.isoformat() if item.reviewed_at else None,
            'updated_at':item.updated_at.isoformat()}

def plan_data(item, coach=False):
    submission = getattr(item,'submission',None)
    state = 'reviewed' if submission and submission.reviewed_at else 'submitted' if submission and submission.submitted_at else 'draft' if submission else 'pending'
    data = {'id':item.id,'title':item.title,'due_date':item.due_date.isoformat(),
            'exercises':item.exercises,'note':item.note,'booking_id':item.booking_id,
            'status':state,'submission':submission_data(submission)}
    if coach:
        data['student'] = student_data(item.student)
    return data
