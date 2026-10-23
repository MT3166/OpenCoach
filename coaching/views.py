import json
import uuid
from datetime import date, timedelta
from functools import wraps
from hashlib import sha256
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, OperationalError
from django.db.models import Count, Q
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from . import accounts, booking, training
from .errors import DomainError
from .forms import LoginForm, RegisterForm, StudentForm, SessionForm, CreditForm, ExerciseForm, PlanForm, FeedbackForm
from .models import Booking, CreditEntry, Invite, Kind, Session, Student, Submission, TrainingPlan, TrainingRecord

def role(staff):
    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.user.is_staff != staff:
                raise PermissionDenied
            if not staff:
                request.student = get_object_or_404(Student, user=request.user)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate

def run_action(request, action, success):
    try:
        result = action()
    except DomainError as exc:
        messages.error(request, str(exc))
        return None, False
    except OperationalError as exc:
        if 'locked' not in str(exc).lower():
            raise
        messages.error(request, '系统繁忙，请稍后重试。重复提交不会再次预约或消课。')
        return None, False
    if success:
        messages.success(request, success)
    return result, True

def init_exercises(form, rows):
    if not form.is_bound:
        form.initial['exercises'] = json.dumps(rows, ensure_ascii=False)
    return form

def wallet(student):
    return [{'kind': kind, 'label': label, **booking.balances(student, kind)} for kind, label in Kind.choices]

@login_required
def home(request):
    return redirect('coach_home' if request.user.is_staff else 'student_home')

def login(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        return redirect('home')
    return render(request, 'login.html', {'form': form})

@require_POST
def logout(request):
    auth_logout(request)
    return redirect('login')

def invite(request, token):
    invitation = Invite.objects.select_related('student').filter(token_hash=sha256(token.encode()).hexdigest()).first()
    valid = bool(invitation and not invitation.used_at and invitation.expires_at > timezone.now() and not invitation.student.user_id)
    form = RegisterForm(request.POST or None)
    if valid and request.method == 'POST' and form.is_valid():
        user, ok = run_action(request, lambda: accounts.accept_invite(token,
            form.cleaned_data['username'], form.cleaned_data['password']), '欢迎加入，开始你的训练旅程。')
        if ok:
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('student_home')
    return render(request, 'invite.html', {'form': form, 'invitation': invitation, 'valid': valid})

@role(True)
def coach_home(request):
    today = timezone.localdate()
    sessions = Session.objects.filter(start__date=today, cancelled=False).annotate(
        occupied=Count('bookings', filter=~Q(bookings__status='cancelled')))
    return render(request, 'coach/home.html', {
        'nav': 'home', 'today': today, 'sessions': sessions,
        'student_count': Student.objects.count(),
        'booking_count': Booking.objects.filter(session__start__date=today).exclude(status='cancelled').count(),
        'pending': Submission.objects.filter(submitted_at__isnull=False, reviewed_at__isnull=True).select_related('plan__student'),
    })

def session_context(request, student=None):
    today = timezone.localdate()
    qs = Session.objects.filter(start__date__gte=today)
    if student:
        qs = qs.filter(start__gt=timezone.now(), cancelled=False)
    day = request.GET.get('day', '')
    if day:
        try:
            qs = qs.filter(start__date=date.fromisoformat(day))
        except ValueError:
            day = ''
    kind = request.GET.get('kind', '')
    if kind in Kind.values:
        qs = qs.filter(kind=kind)
    else:
        kind = ''
    sessions = list(qs.annotate(occupied=Count('bookings', filter=~Q(bookings__status='cancelled'))))
    enrolled = set(student.bookings.exclude(status='cancelled').values_list('session_id', flat=True)) if student else set()
    for item in sessions:
        item.slots_left = item.capacity - item.occupied
        item.enrolled = item.pk in enrolled
        item.operation_key = uuid.uuid4()
    return {'sessions': sessions, 'day': day, 'kind': kind, 'today': today,
            'days': [today + timedelta(days=i) for i in range(7)], 'kinds': Kind.choices}

@role(True)
def coach_sessions(request):
    form = SessionForm(request.POST or None, initial={'title': '力量与动作控制', 'kind': 'private', 'capacity': 1, 'location': '松间训练室'})
    if request.method == 'POST' and form.is_valid():
        _, ok = run_action(request, lambda: booking.create_session(**form.cleaned_data), '课程已发布，学员可以预约了。')
        if ok:
            return redirect('coach_sessions')
    return render(request, 'coach/sessions.html', {'nav': 'sessions', 'form': form, **session_context(request)})

@role(True)
def coach_session(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if request.method == 'POST':
        _, ok = run_action(request, lambda: booking.cancel_session(pk, request.user), '课程已取消，未消耗课时已释放。')
        if ok:
            return redirect('coach_sessions')
    return render(request, 'coach/session.html', {'nav': 'sessions', 'session': session,
        'bookings': session.bookings.select_related('student').order_by('created_at')})

@role(True)
def coach_students(request):
    form = StudentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        student, ok = run_action(request, lambda: accounts.create_student(form.cleaned_data['name']), '学员档案已创建。')
        if ok:
            return redirect('coach_student', pk=student.id)
    students = Student.objects.select_related('user').order_by('-created_at')
    if request.GET.get('q'):
        students = students.filter(name__icontains=request.GET['q'])
    return render(request, 'coach/students.html', {'nav': 'students', 'students': students, 'form': form})

@role(True)
def coach_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    credit_form = CreditForm(request.POST if request.POST.get('action') == 'credit' else None,
                             initial={'operation_key': uuid.uuid4()})
    plan_form = init_exercises(PlanForm(request.POST if request.POST.get('action') == 'plan' else None,
        initial={'due_date': timezone.localdate() + timedelta(days=1)}), [])
    invite_url = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'invite':
            token, ok = run_action(request, lambda: accounts.issue_invite(student), '邀请链接已生成，有效期 7 天。')
            if ok:
                invite_url = request.build_absolute_uri('/invite/' + token + '/')
        elif action == 'credit' and credit_form.is_valid():
            _, ok = run_action(request, lambda: booking.add_credit(student, **credit_form.cleaned_data), '课包购买次数已录入。')
            if ok:
                return redirect('coach_student', pk=pk)
        elif action == 'plan' and plan_form.is_valid():
            plan, ok = run_action(request, lambda: training.create_plan(student, request.user, **plan_form.cleaned_data), '课后计划已布置。')
            if ok:
                return redirect('coach_plan', pk=plan.id)
    return render(request, 'coach/student.html', {'nav': 'students', 'student': student,
        'wallet': wallet(student), 'credit_form': credit_form, 'plan_form': plan_form, 'invite_url': invite_url,
        'bookings': student.bookings.select_related('session')[:8],
        'plans': student.plans.select_related('submission'), 'credits': student.credits.all()[:12]})

@role(True)
def coach_booking(request, pk):
    item = get_object_or_404(Booking.objects.select_related('student', 'session'), pk=pk)
    record = TrainingRecord.objects.filter(booking=item).first()
    record_form = init_exercises(ExerciseForm(request.POST if request.POST.get('action') == 'record' else None, auto_id='record_%s',
        initial={'note': record.note if record else ''}), record.exercises if record else [])
    plan_form = init_exercises(PlanForm(request.POST if request.POST.get('action') == 'plan' else None, auto_id='plan_%s',
        initial={'due_date': timezone.localdate() + timedelta(days=1)}), record.exercises if record else [])
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'finish':
            _, ok = run_action(request, lambda: booking.finish(pk, request.user, request.POST.get('outcome')), '出勤已确认，课时账目已同步。')
            if ok:
                return redirect('coach_booking', pk=pk)
        elif action == 'cancel':
            _, ok = run_action(request, lambda: booking.cancel(pk, request.user), '预约已取消，课时已释放。')
            if ok:
                return redirect('coach_booking', pk=pk)
        elif action == 'record' and record_form.is_valid():
            _, ok = run_action(request, lambda: training.save_record(pk, request.user, **record_form.cleaned_data), '训练记录已保存，学员可以查看。')
            if ok:
                return redirect('coach_booking', pk=pk)
        elif action == 'plan' and plan_form.is_valid():
            plan, ok = run_action(request, lambda: training.create_plan(item.student, request.user,
                booking=item, **plan_form.cleaned_data), '课后计划已布置。')
            if ok:
                return redirect('coach_plan', pk=plan.id)
    return render(request, 'coach/booking.html', {'nav': 'sessions', 'booking': item,
        'record_form': record_form, 'plan_form': plan_form, 'now': timezone.now()})

@role(True)
def coach_plan(request, pk):
    plan = get_object_or_404(TrainingPlan.objects.select_related('student', 'booking__session'), pk=pk)
    submission = Submission.objects.filter(plan=plan).first()
    form = FeedbackForm(request.POST or None, initial={'feedback': submission.feedback if submission else ''})
    if request.method == 'POST' and form.is_valid():
        if not submission:
            messages.error(request, '学员还未提交训练。')
        else:
            _, ok = run_action(request, lambda: training.review_submission(submission.id, request.user,
                form.cleaned_data['feedback']), '点评已发送给学员。')
            if ok:
                return redirect('coach_plan', pk=pk)
    return render(request, 'coach/plan.html', {'nav': 'home', 'plan': plan, 'submission': submission, 'form': form})

@role(False)
def student_home(request):
    student = request.student
    upcoming = student.bookings.filter(status='booked', session__end__gt=timezone.now()).select_related('session').order_by('session__start')[:3]
    return render(request, 'student/home.html', {'nav': 'home', 'student': student, 'wallet': wallet(student),
        'upcoming': upcoming, 'plans': student.plans.select_related('submission')[:4],
        'completed': student.bookings.filter(status='completed').count(), 'today': timezone.localdate()})

@role(False)
def student_sessions(request):
    if request.method == 'POST':
        try:
            session_id = int(request.POST.get('session_id', ''))
        except ValueError:
            raise Http404
        item, ok = run_action(request, lambda: booking.reserve(request.student, session_id,
            request.POST.get('operation_key')), '')
        if ok:
            if item.status == Booking.Status.BOOKED:
                messages.success(request, '预约成功，这节课的名额已为你保留。')
            else:
                messages.info(request, '这笔预约的当前状态是“' + item.get_status_display() + '”，请查看现有记录。')
            return redirect('student_bookings')
    return render(request, 'student/sessions.html', {'nav': 'sessions', 'wallet': wallet(request.student), **session_context(request, request.student)})

@role(False)
def student_bookings(request):
    items = request.student.bookings.select_related('session', 'record')
    now = timezone.now()
    for item in items:
        item.can_cancel = item.status == 'booked' and now <= item.session.start - timedelta(hours=12)
    return render(request, 'student/bookings.html', {'nav': 'sessions', 'bookings': items})

@role(False)
@require_POST
def student_cancel(request, pk):
    run_action(request, lambda: booking.cancel(pk, request.user), '预约已取消，课时已释放。')
    return redirect('student_bookings')

@role(False)
def student_training(request):
    return render(request, 'student/training.html', {'nav': 'training',
        'plans': request.student.plans.select_related('submission'),
        'records': TrainingRecord.objects.filter(booking__student=request.student).select_related('booking__session')})

@role(False)
def student_plan(request, pk):
    plan = get_object_or_404(TrainingPlan, pk=pk, student=request.student)
    submission = Submission.objects.filter(plan=plan).first()
    rows = submission.exercises if submission else [{'name': row['name']} for row in plan.exercises]
    form = init_exercises(ExerciseForm(request.POST or None,
        initial={'note': submission.note if submission else ''}), rows)
    if request.method == 'POST' and form.is_valid():
        intent = request.POST.get('intent')
        if intent not in ['draft', 'submit']:
            raise PermissionDenied
        _, ok = run_action(request, lambda: training.save_submission(pk, request.user,
            **form.cleaned_data, submit=intent == 'submit'), '训练已提交，等待教练点评。' if intent == 'submit' else '草稿已保存，可以稍后继续。')
        if ok:
            return redirect('student_plan', pk=pk)
    return render(request, 'student/plan.html', {'nav': 'training', 'plan': plan, 'submission': submission, 'form': form})

@role(False)
def student_profile(request):
    return render(request, 'student/profile.html', {'nav': 'profile', 'student': request.student,
        'wallet': wallet(request.student), 'credits': request.student.credits.select_related('booking__session')[:20]})

def health(request):
    try:
        Student.objects.exists()
        return JsonResponse({'status': 'ok'})
    except DatabaseError:
        return JsonResponse({'status': 'unavailable'}, status=503)
