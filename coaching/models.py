from django.conf import settings
from django.db import models
from django.db.models import Q, F

class Kind(models.TextChoices):
    PRIVATE = 'private', '一对一私教'
    GROUP = 'group', '小班课'

class Student(models.Model):
    name = models.CharField(max_length=50)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.PROTECT, related_name='student')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Invite(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='invites')
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)

class Session(models.Model):
    title = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    start = models.DateTimeField()
    end = models.DateTimeField()
    location = models.CharField(max_length=120)
    capacity = models.PositiveIntegerField(default=1)
    cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ['start', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(end__gt=F('start')), name='session_valid_interval'),
            models.CheckConstraint(condition=(Q(kind='private', capacity=1) | Q(kind='group', capacity__gte=2)),
                                   name='session_valid_capacity'),
        ]

class Booking(models.Model):
    class Status(models.TextChoices):
        BOOKED = 'booked', '已预约'
        COMPLETED = 'completed', '已完课'
        CANCELLED = 'cancelled', '已取消'
        NO_SHOW_CHARGED = 'no_show_charged', '缺席已消课'
        NO_SHOW_WAIVED = 'no_show_waived', '缺席免消课'

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='bookings')
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='bookings')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)
    operation_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rescheduled_from = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT,
                                            related_name='rescheduled_to')

    class Meta:
        ordering = ['-session__start', '-id']
        constraints = [models.UniqueConstraint(fields=['student', 'session'],
                       condition=~Q(status='cancelled'), name='one_active_booking')]

class CreditEntry(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='credits')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    entry_type = models.CharField(max_length=10, choices=[('purchase', '购买录入'), ('consume', '课程消耗')])
    units = models.PositiveIntegerField()
    booking = models.OneToOneField(Booking, null=True, on_delete=models.PROTECT, related_name='charge')
    direct_lesson = models.OneToOneField('DirectLesson', null=True, blank=True,
                                       on_delete=models.PROTECT, related_name='charge')
    operation_key = models.UUIDField(null=True, unique=True)
    expires_on = models.DateField(null=True, blank=True)
    purchase = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='consumptions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(
            condition=(Q(entry_type='purchase', units__gt=0, booking__isnull=True,
                         direct_lesson__isnull=True, operation_key__isnull=False)
                       | (Q(entry_type='consume', units=1, operation_key__isnull=True)
                          & (Q(booking__isnull=False, direct_lesson__isnull=True)
                             | Q(booking__isnull=True, direct_lesson__isnull=False)))),
            name='valid_credit_entry')]

class TrainingRecord(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name='record')
    exercises = models.JSONField(default=list)
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

class TrainingPlan(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='plans')
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.PROTECT)
    title = models.CharField(max_length=80)
    due_date = models.DateField()
    exercises = models.JSONField(default=list)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date', '-id']

class Submission(models.Model):
    plan = models.OneToOneField(TrainingPlan, on_delete=models.PROTECT, related_name='submission')
    exercises = models.JSONField(default=list)
    note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True)
    feedback = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

class DirectLesson(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='direct_lessons')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    occurred_on = models.DateField()
    exercises = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True)
    operation_key = models.UUIDField(unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-occurred_on', '-id']


class LessonBatch(models.Model):
    operation_key = models.UUIDField(unique=True)
    payload = models.JSONField()
    lesson_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class Waitlist(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='waitlist')
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='waitlist')
    status = models.CharField(max_length=12, choices=[('waiting','候补中'),('promoted','已递补'),('cancelled','已退出')], default='waiting')
    operation_key = models.UUIDField(unique=True)
    booking = models.OneToOneField(Booking, null=True, blank=True, on_delete=models.PROTECT, related_name='waitlist_origin')
    created_at = models.DateTimeField(auto_now_add=True)
    promoted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(fields=['student','session'], condition=Q(status='waiting'), name='one_waiting_per_course'),
            models.CheckConstraint(condition=(Q(status='promoted', booking__isnull=False, promoted_at__isnull=False)
                | Q(status__in=['waiting','cancelled'], booking__isnull=True, promoted_at__isnull=True)), name='valid_waitlist_state'),
        ]
