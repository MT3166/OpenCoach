from django.db import transaction
from django.db.models import Count, Q, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from coaching import booking
from coaching.models import Session, Booking, Student, TrainingRecord, Kind, Waitlist
from .common import CoachView, StudentView, InputSerializer, StrictIntegerField, validated, success, paginate, query_day, query_choice, query_int
from .serializers import course_data, booking_data, student_data, record_data

class ZonedDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        try:
            parsed = parse_datetime(value) if isinstance(value,str) else None
        except (ValueError,TypeError):
            parsed = None
        if parsed is None or timezone.is_naive(parsed):
            raise serializers.ValidationError('请提供含时区的完整时间')
        return super().to_internal_value(value)

class SessionInput(InputSerializer):
    title = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=Kind.choices)
    start = ZonedDateTimeField()
    end = ZonedDateTimeField()
    location = serializers.CharField(max_length=120)
    capacity = StrictIntegerField(min_value=1,max_value=100)
    def validate(self, attrs):
        if attrs['end'] <= attrs['start']:
            raise serializers.ValidationError({'end':['结束时间须晚于开始时间']})
        if attrs['kind']=='private' and attrs['capacity']!=1:
            raise serializers.ValidationError({'capacity':['私教容量固定为1']})
        if attrs['kind']=='group' and attrs['capacity']<2:
            raise serializers.ValidationError({'capacity':['小班至少2人']})
        return attrs

class ReserveInput(InputSerializer):
    session_id = StrictIntegerField(min_value=1)
    operation_key = serializers.UUIDField()

class FinishInput(InputSerializer):
    outcome = serializers.ChoiceField(choices=['completed','no_show_charged','no_show_waived'])

def session_queryset(request, student=None):
    queryset = Session.objects.annotate(occupied=Count('bookings',filter=~Q(bookings__status='cancelled'))).order_by('start','id')
    day = query_day(request)
    kind = query_choice(request,'kind',Kind.values)
    if day:
        queryset = queryset.filter(start__date=day)
    elif not student:
        queryset = queryset.filter(start__date__gte=timezone.localdate())
    if kind:
        queryset = queryset.filter(kind=kind)
    if student:
        queryset = queryset.filter(start__gt=timezone.now(),cancelled=False).annotate(my_booking_id=Subquery(
            Booking.objects.filter(student=student,session_id=OuterRef('pk')).exclude(status='cancelled').values('id')[:1]),
            my_waitlist_id=Subquery(Waitlist.objects.filter(student=student,session_id=OuterRef('pk'),status='waiting').values('id')[:1]))
    return queryset

def booking_queryset(request, student=None):
    queryset = Booking.objects.select_related('student','session','record').order_by('-session__start','-id')
    if student:
        queryset = queryset.filter(student=student)
    else:
        student_id = query_int(request,'student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
    day, kind = query_day(request), query_choice(request,'kind',Kind.values)
    status = query_choice(request,'status',Booking.Status.values)
    if day:
        queryset = queryset.filter(session__start__date=day)
    if kind:
        queryset = queryset.filter(session__kind=kind)
    if status:
        queryset = queryset.filter(status=status)
    return queryset

class CoachSessionsView(CoachView):
    def get(self, request):
        return success(paginate(request,session_queryset(request),course_data))
    def post(self, request):
        return success(course_data(booking.create_session(**validated(SessionInput,request))),201)

class StudentSessionsView(StudentView):
    def get(self, request):
        return success(paginate(request,session_queryset(request,request.student),course_data))

class SessionDetailView(CoachView):
    def get(self, request, pk):
        return success(course_data(get_object_or_404(Session,pk=pk)))

class SessionBookingsView(CoachView):
    def get(self, request, pk):
        get_object_or_404(Session,pk=pk)
        queryset = Booking.objects.filter(session_id=pk).select_related('student','session').order_by('created_at','id')
        return success(paginate(request,queryset,lambda item:booking_data(item,True)))

class CancelSessionView(CoachView):
    def post(self, request, pk):
        return success(course_data(booking.cancel_session(pk,request.user)))

class CoachBookingsView(CoachView):
    def get(self, request):
        return success(paginate(request,booking_queryset(request),lambda item:booking_data(item,True)))

class StudentBookingsView(StudentView):
    def get(self, request):
        return success(paginate(request,booking_queryset(request,request.student),booking_data))
    def post(self, request):
        data = validated(ReserveInput,request)
        with transaction.atomic():
            old = Booking.objects.filter(operation_key=data['operation_key']).exists()
            item = booking.reserve(request.student,**data)
        return success(booking_data(item),200 if old else 201)

class BookingDetailView(CoachView):
    def get(self, request, pk):
        item = get_object_or_404(Booking.objects.select_related('student','session','record'),pk=pk)
        return success({'booking':booking_data(item,True),'student':student_data(item.student),'record':record_data(getattr(item,'record',None))})

class CoachCancelBookingView(CoachView):
    def post(self, request, pk):
        return success(booking_data(booking.cancel(pk,request.user),True))

class StudentCancelBookingView(StudentView):
    def post(self, request, pk):
        get_object_or_404(Booking,pk=pk,student=request.student)
        return success(booking_data(booking.cancel(pk,request.user)))

class FinishBookingView(CoachView):
    def post(self, request, pk):
        return success(booking_data(booking.finish(pk,request.user,**validated(FinishInput,request)),True))

class CoachRescheduleView(CoachView):
    def post(self, request, pk):
        return success(booking_data(booking.reschedule(pk, request.user, **validated(ReserveInput, request)), True))

class StudentRescheduleView(StudentView):
    def post(self, request, pk):
        get_object_or_404(Booking, pk=pk, student=request.student)
        return success(booking_data(booking.reschedule(pk, request.user, **validated(ReserveInput, request))))
