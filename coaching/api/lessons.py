from django.db import transaction
from django.db.models import Value, CharField
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from coaching import lessons
from coaching.errors import DomainError
from coaching.models import DirectLesson, Booking, Student, Kind
from .common import CoachView, StudentView, InputSerializer, StrictIntegerField, validated, success, query_day, query_int, query_choice
from .serializers import lesson_data, wallets

class NoteInput(InputSerializer):
    note = serializers.CharField(max_length=4000,allow_blank=True,required=False,default='')
    exercises = serializers.JSONField(required=False)
    def validate_exercises(self, value):
        try:
            return lessons.optional_exercises(value)
        except DomainError as exc:
            raise serializers.ValidationError(str(exc)) from exc

class DirectInput(NoteInput):
    student_id = StrictIntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=Kind.choices)
    occurred_on = serializers.DateField()
    operation_key = serializers.UUIDField()
    def validate_occurred_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('只能记录已上课的日期')
        return value

class PatchNoteInput(NoteInput):
    note = serializers.CharField(max_length=4000,allow_blank=True,required=False)

class BatchItemInput(NoteInput):
    student_id = StrictIntegerField(min_value=1)
    operation_key = serializers.UUIDField()

class BatchInput(InputSerializer):
    kind = serializers.ChoiceField(choices=Kind.choices)
    occurred_on = serializers.DateField()
    operation_key = serializers.UUIDField()
    items = BatchItemInput(many=True, allow_empty=False, max_length=100)

    def validate_occurred_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('只能记录已上课的日期')
        return value

    def validate_items(self, value):
        if len({row['student_id'] for row in value}) != len(value) or len({row['operation_key'] for row in value}) != len(value):
            raise serializers.ValidationError('同批学员与操作标识不能重复')
        return value

def history_data(request, student=None, limit=None):
    direct = DirectLesson.objects.all()
    booked = Booking.objects.filter(status='completed')
    if student:
        direct, booked = direct.filter(student=student), booked.filter(student=student)
    day, kind = query_day(request), query_choice(request,'kind',Kind.values)
    if day:
        direct, booked = direct.filter(occurred_on=day), booked.filter(session__start__date=day)
    if kind:
        direct, booked = direct.filter(kind=kind), booked.filter(session__kind=kind)
    direct_rows = direct.order_by().annotate(source=Value('direct',output_field=CharField())).values('pk','occurred_on','source')
    booking_rows = booked.order_by().annotate(occurred_on=TruncDate('session__start'),source=Value('booking',output_field=CharField())).values('pk','occurred_on','source')
    combined = direct_rows.union(booking_rows).order_by('-occurred_on','source','-pk')
    page = query_int(request,'page',1)
    size = limit or query_int(request,'page_size',30,maximum=100)
    rows = list(combined[(page-1)*size:page*size])
    direct_objects = {item.pk:item for item in direct.filter(pk__in=[row['pk'] for row in rows if row['source']=='direct']).select_related('student')}
    booking_objects = {item.pk:item for item in booked.filter(pk__in=[row['pk'] for row in rows if row['source']=='booking']).select_related('student','session','record')}
    items = [lesson_data((direct_objects if row['source']=='direct' else booking_objects)[row['pk']],row['source']) for row in rows]
    return {'items':items,'pagination':{'page':page,'page_size':size,'total':combined.count()}}

def lesson_result(item):
    return {'lesson':lesson_data(item,'direct'),'wallets':wallets(item.student)}

class CoachLessonsView(CoachView):
    def get(self, request):
        student_id = query_int(request,'student_id')
        student = get_object_or_404(Student,pk=student_id) if student_id else None
        return success(history_data(request,student))
    def post(self, request):
        data = validated(DirectInput,request)
        student = get_object_or_404(Student,pk=data.pop('student_id'))
        with transaction.atomic():
            old = DirectLesson.objects.filter(operation_key=data['operation_key']).exists()
            item = lessons.record_direct_lesson(student,request.user,**data)
        return success(lesson_result(item),200 if old else 201)

class CoachLessonView(CoachView):
    def get(self, request, pk):
        return success(lesson_result(get_object_or_404(DirectLesson.objects.select_related('student'),pk=pk)))
    def patch(self, request, pk):
        return success(lesson_result(lessons.update_lesson_note(pk,request.user,**validated(PatchNoteInput,request))))

class StudentLessonsView(StudentView):
    def get(self, request):
        return success(history_data(request,request.student))

class StudentLessonView(StudentView):
    def get(self, request, pk):
        item = get_object_or_404(DirectLesson,pk=pk,student=request.student)
        return success(lesson_result(item))

class CoachBatchLessonsView(CoachView):
    def post(self, request):
        with transaction.atomic():
            items = lessons.record_batch(request.user, **validated(BatchInput, request))
            return success({'items':[lesson_data(item, 'direct') for item in items],
                            'wallets':[{'student_id':item.student_id,'wallets':wallets(item.student)} for item in items]})
