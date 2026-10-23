from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from coaching import waitlist
from coaching.models import Session, Waitlist
from .common import CoachView, StudentView, InputSerializer, validated, success, paginate
from .serializers import course_data, student_data


class JoinInput(InputSerializer):
    operation_key = serializers.UUIDField()


def waitlist_data(item, coach=False):
    position = None
    if item.status == 'waiting':
        position = Waitlist.objects.filter(session_id=item.session_id, status='waiting').filter(
            Q(created_at__lt=item.created_at) | Q(created_at=item.created_at, pk__lte=item.pk)).count()
    data = {'id':item.pk, 'status':item.status, 'session':course_data(item.session),
            'created_at':item.created_at.isoformat(), 'position':position,
            'promoted_at':item.promoted_at.isoformat() if item.promoted_at else None, 'booking_id':item.booking_id}
    if coach:
        data['student'] = student_data(item.student)
    return data


class JoinWaitlistView(StudentView):
    def post(self, request, pk):
        with transaction.atomic():
            return success(waitlist_data(waitlist.join(request.student, pk, **validated(JoinInput,request))))


class LeaveWaitlistView(StudentView):
    def post(self, request, pk):
        return success(waitlist_data(waitlist.leave(pk,request.student)))


class StudentWaitlistView(StudentView):
    def get(self, request):
        return success(paginate(request, Waitlist.objects.filter(student=request.student).select_related('session'),waitlist_data))


class CoachWaitlistView(CoachView):
    def get(self, request, pk):
        get_object_or_404(Session,pk=pk)
        return success(paginate(request,Waitlist.objects.filter(session_id=pk).select_related('session','student'),lambda item:waitlist_data(item,True)))
