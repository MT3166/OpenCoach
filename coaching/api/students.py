from datetime import timedelta
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from coaching import accounts, booking
from coaching.models import Student, CreditEntry, Kind, Booking
from .common import CoachView, StudentView, InputSerializer, StrictIntegerField, validated, success, paginate, query_choice
from .serializers import student_data, wallets, credit_data

class StudentInput(InputSerializer):
    name = serializers.CharField(max_length=50)

class CreditInput(InputSerializer):
    kind = serializers.ChoiceField(choices=Kind.choices)
    units = StrictIntegerField(min_value=1,max_value=10000)
    operation_key = serializers.UUIDField()
    expires_on = serializers.DateField(required=False, allow_null=True, default=None)

class StudentsView(CoachView):
    def get(self, request):
        queryset = Student.objects.order_by('-created_at','-id')
        if request.query_params.get('q'):
            queryset = queryset.filter(name__icontains=request.query_params['q'][:150])
        return success(paginate(request,queryset,student_data))
    def post(self, request):
        item = accounts.create_student(**validated(StudentInput,request))
        return success(student_data(item),201)

def attendance(student):
    today = timezone.localdate()
    month = today.replace(day=1)
    booked = student.bookings.filter(session__start__date__gte=month,session__start__date__lte=today)
    arrived = booked.filter(status='completed').count()
    missed = booked.filter(status__in=['no_show_charged','no_show_waived']).count()
    return {'period':month.strftime('%Y-%m'),'scheduled_attended':arrived,'scheduled_missed':missed,
            'scheduled_cancelled':booked.filter(status='cancelled').count(),
            'pending':booked.filter(status='booked',session__start__lte=timezone.now()).count(),
            'direct_attended':student.direct_lessons.filter(occurred_on__gte=month,occurred_on__lte=today).count(),
            'scheduled_rate':round(arrived/(arrived+missed)*100,1) if arrived+missed else None}

class StudentDetailView(CoachView):
    def get(self, request, pk):
        student = get_object_or_404(Student,pk=pk)
        return success({'student':student_data(student),'wallets':wallets(student),'attendance':attendance(student)})

class InviteStudentView(CoachView):
    def post(self, request, pk):
        student = get_object_or_404(Student,pk=pk)
        token = accounts.issue_invite(student)
        return success({'url':request.build_absolute_uri(f'/invite/{token}/'),
                        'expires_at':student.invites.get().expires_at.isoformat()},201)

class StudentCreditsView(CoachView):
    def get(self, request, pk):
        student = get_object_or_404(Student,pk=pk)
        queryset = student.credits.select_related('booking__session','direct_lesson').order_by('-created_at','-id')
        kind = query_choice(request,'kind',Kind.values)
        if kind:
            queryset = queryset.filter(kind=kind)
        return success(paginate(request,queryset,credit_data))
    def post(self, request, pk):
        student = get_object_or_404(Student,pk=pk)
        data = validated(CreditInput,request)
        with transaction.atomic():
            old = CreditEntry.objects.filter(operation_key=data['operation_key']).exists()
            entry = booking.add_credit(student,**data)
        return success({'entry':credit_data(entry),'wallets':wallets(student)},200 if old else 201)

class ProfileView(StudentView):
    def get(self, request):
        return success({'student':student_data(request.student),'wallets':wallets(request.student)})

class CreditsView(StudentView):
    def get(self, request):
        queryset = request.student.credits.select_related('booking__session','direct_lesson').order_by('-created_at','-id')
        kind = query_choice(request,'kind',Kind.values)
        if kind:
            queryset = queryset.filter(kind=kind)
        return success(paginate(request,queryset,credit_data))
