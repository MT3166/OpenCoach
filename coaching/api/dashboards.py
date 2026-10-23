from django.db.models import Count, Q
from django.utils import timezone
from coaching.models import Session, Student, Booking, Submission, DirectLesson
from .common import CoachView, StudentView, success
from .serializers import course_data, booking_data, wallets, plan_data, student_data
from .lessons import history_data

class CoachDashboardView(CoachView):
    def get(self, request):
        today = timezone.localdate()
        sessions = Session.objects.filter(start__date=today,cancelled=False).annotate(occupied=Count('bookings',filter=~Q(bookings__status='cancelled')))
        pending = Submission.objects.filter(submitted_at__isnull=False,reviewed_at__isnull=True).select_related('plan__student').order_by('submitted_at','id')
        unconfirmed = Booking.objects.filter(status='booked',session__start__lte=timezone.now(),session__cancelled=False).select_related('student','session').order_by('session__start','id')
        return success({'today':today.isoformat(),'student_count':Student.objects.count(),
            'booking_count':Booking.objects.filter(session__start__date=today).exclude(status='cancelled').count(),
            'sessions':[course_data(item) for item in sessions], 'pending_count':pending.count(),
            'pending':[{'submission_id':item.id,'plan_id':item.plan_id,'student_name':item.plan.student.name,'title':item.plan.title} for item in pending[:5]],
            'unconfirmed_count':unconfirmed.count(),'unconfirmed':[booking_data(item,True) for item in unconfirmed[:10]],
            'recorded_today':DirectLesson.objects.filter(occurred_on=today).count()+Booking.objects.filter(status='completed',session__start__date=today).count(),
            'recent_lessons':history_data(request,limit=5)['items']})

class StudentDashboardView(StudentView):
    def get(self, request):
        student = request.student
        upcoming = student.bookings.filter(status='booked',session__end__gt=timezone.now()).select_related('session').order_by('session__start')[:3]
        plans = student.plans.filter(Q(submission__isnull=True)|Q(submission__submitted_at__isnull=True)).select_related('submission')[:4]
        return success({'today':timezone.localdate().isoformat(),'student':student_data(student),'wallets':wallets(student),
            'upcoming':[booking_data(item) for item in upcoming], 'plans':[plan_data(item) for item in plans],
            'completed_count':student.bookings.filter(status='completed').count()+student.direct_lessons.count(),
            'recent_lessons':history_data(request,student,limit=3)['items']})
