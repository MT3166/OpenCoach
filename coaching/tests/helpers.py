import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from coaching.models import Student, Session, CreditEntry, Kind

def make_student(name, credits=2, kind=Kind.PRIVATE):
    user = get_user_model().objects.create(username=name)
    student = Student.objects.create(name=name, user=user)
    if credits:
        CreditEntry.objects.create(student=student, kind=kind, entry_type='purchase',
                                   units=credits, operation_key=uuid.uuid4())
    return student

def make_session(offset=30, kind=Kind.PRIVATE, capacity=1):
    start = timezone.now() + timedelta(hours=offset)
    return Session.objects.create(title='力量训练', kind=kind, start=start,
        end=start + timedelta(hours=1), location='松间训练室', capacity=capacity)
