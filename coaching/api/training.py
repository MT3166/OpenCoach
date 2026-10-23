from django.shortcuts import get_object_or_404
from rest_framework import serializers
from coaching import training
from coaching.errors import DomainError
from coaching.models import Booking, Student, TrainingPlan, TrainingRecord, Submission
from .common import CoachView, StudentView, InputSerializer, StrictIntegerField, validated, success, paginate, query_int
from .lessons import NoteInput
from .serializers import plan_data, record_data, submission_data

class PlanInput(NoteInput):
    student_id = StrictIntegerField(min_value=1)
    booking_id = StrictIntegerField(min_value=1,allow_null=True,required=False,default=None)
    title = serializers.CharField(max_length=80)
    due_date = serializers.DateField()
    exercises = serializers.JSONField()
    def validate_exercises(self, value):
        try:
            return training.validate_exercises(value)
        except DomainError as exc:
            raise serializers.ValidationError(str(exc)) from exc

class SubmissionInput(PlanInput):
    student_id = None
    booking_id = None
    title = None
    due_date = None
    intent = serializers.ChoiceField(choices=['draft','submit'])

class FeedbackInput(InputSerializer):
    feedback = serializers.CharField(max_length=4000)

class RecordView(CoachView):
    def put(self, request, pk):
        data = validated(NoteInput,request)
        return success(record_data(training.save_record(pk,request.user,data.get('exercises',[]),data['note'])))

class CoachPlansView(CoachView):
    def get(self, request):
        queryset = TrainingPlan.objects.select_related('student','submission').order_by('due_date','-id')
        student_id = query_int(request,'student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return success(paginate(request,queryset,lambda item:plan_data(item,True)))
    def post(self, request):
        data = validated(PlanInput,request)
        student = get_object_or_404(Student,pk=data.pop('student_id'))
        booking_id = data.pop('booking_id')
        item = get_object_or_404(Booking,pk=booking_id,student=student) if booking_id else None
        return success(plan_data(training.create_plan(student,request.user,booking=item,**data),True),201)

class CoachPlanView(CoachView):
    def get(self, request, pk):
        return success(plan_data(get_object_or_404(TrainingPlan.objects.select_related('student','submission'),pk=pk),True))

class StudentPlansView(StudentView):
    def get(self, request):
        queryset = request.student.plans.select_related('submission').order_by('due_date','-id')
        return success(paginate(request,queryset,plan_data))

class StudentPlanView(StudentView):
    def get(self, request, pk):
        return success(plan_data(get_object_or_404(TrainingPlan.objects.select_related('submission'),pk=pk,student=request.student)))

class SubmissionView(StudentView):
    def put(self, request, pk):
        get_object_or_404(TrainingPlan,pk=pk,student=request.student)
        data = validated(SubmissionInput,request)
        intent = data.pop('intent')
        return success(submission_data(training.save_submission(pk,request.user,submit=intent=='submit',**data)))

class FeedbackView(CoachView):
    def put(self, request, pk):
        return success(submission_data(training.review_submission(pk,request.user,**validated(FeedbackInput,request))))

class StudentRecordsView(StudentView):
    def get(self, request):
        queryset = TrainingRecord.objects.filter(booking__student=request.student).select_related('booking__session').order_by('-booking__session__start','-id')
        return success(paginate(request,queryset,record_data))
