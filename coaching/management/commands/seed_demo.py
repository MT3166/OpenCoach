import json
import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from coaching.booking import add_credit, finish
from coaching.models import Booking, CreditEntry, Kind, Session, Student
from coaching.training import create_plan, save_record, save_submission, review_submission

MARKER = uuid.uuid5(uuid.NAMESPACE_URL, 'opencoach-demo/initial')

class Command(BaseCommand):
    help = '初始化演示账号和训练数据'

    def handle(self, **options):
        with transaction.atomic():
            if CreditEntry.objects.filter(operation_key=MARKER).exists():
                self.stdout.write(json.dumps({'already_initialized': True}))
                return
            credentials = []
            User = get_user_model()

            def user(username, name, staff=False):
                existing = User.objects.filter(username=username).first()
                if existing:
                    if existing.is_staff != staff:
                        raise CommandError('演示账号名称与现有账号角色冲突')
                    return existing
                password = secrets.token_urlsafe(12)
                created = User.objects.create_user(username=username, password=password,
                                                  first_name=name, is_staff=staff)
                credentials.append({'username': username, 'password': password,
                                    'name': name, 'role': 'coach' if staff else 'student'})
                return created

            coach = User.objects.filter(is_staff=True).first() or user('coach', settings.COACH_NAME, True)
            a_user = user('xiaoyu', '陈可欣')
            b_user = user('achen', '周予安')
            a, _ = Student.objects.get_or_create(user=a_user, defaults={'name': '陈可欣'})
            b, _ = Student.objects.get_or_create(user=b_user, defaults={'name': '周予安'})
            Student.objects.get_or_create(name='许一诺', user=None)
            for student in [a, b]:
                for kind, units in [(Kind.PRIVATE, 12), (Kind.GROUP, 8)]:
                    key = MARKER if student == a and kind == Kind.PRIVATE else uuid.uuid5(
                        uuid.NAMESPACE_URL, f'opencoach-demo/{student.user.username}/{kind}')
                    add_credit(student, kind, units, key)
            now = timezone.now()

            def session(title, offset, kind=Kind.PRIVATE, capacity=1):
                start = now + timedelta(hours=offset)
                return Session.objects.create(title=title, kind=kind, start=start,
                    end=start + timedelta(hours=1), location='松间训练室 · 2F', capacity=capacity)

            ongoing = session('力量基础 · 动作控制', -.5)
            session('下肢力量 · 一对一', 3)
            session('上肢力量 · 一对一', 22)
            group = session('普拉提 · 核心稳定', 26, Kind.GROUP, 6)
            past = session('全身力量 · 基础', -26)
            pilates = session('普拉提 · 呼吸与核心', -50, Kind.GROUP, 4)
            def enrollment(student, course):
                return Booking.objects.create(student=student, session=course, operation_key=uuid.uuid4())
            enrollment(a, ongoing)
            enrollment(b, group)
            a_done = enrollment(a, past)
            b_done = enrollment(b, pilates)
            finish(a_done.id, coach, 'completed')
            finish(b_done.id, coach, 'completed')
            strength = [
                {'name': '高脚杯深蹲', 'sets': 3, 'reps': 12, 'weight': '8'},
                {'name': '俯身划船', 'sets': 3, 'reps': 10, 'weight': '6'},
                {'name': '平板支撑', 'sets': 3, 'duration': 30},
            ]
            mobility = [
                {'name': '死虫式', 'sets': 3, 'reps': 12, 'weight': '0'},
                {'name': '臀桥', 'sets': 3, 'reps': 15, 'weight': '0'},
                {'name': '侧支撑', 'sets': 2, 'duration': 25},
            ]
            save_record(a_done.id, coach, strength, '深蹲动作更稳定，下一次继续关注下降速度与膝盖方向。')
            save_record(b_done.id, coach, mobility, '呼吸节奏有进步，侧支撑优先保持身体对齐。')
            create_plan(a, coach, '下肢稳定 · 自主练习', timezone.localdate() + timedelta(days=1),
                        strength, '动作放慢，保持呼吸。每组之间休息 60 秒。', a_done)
            pending = create_plan(a, coach, '肩背激活 · 课后复盘', timezone.localdate(),
                [{'name': '俯身划船', 'sets': 3, 'reps': 12, 'weight': '6'},
                 {'name': '肩胛俯卧撑', 'sets': 2, 'reps': 12, 'weight': '0'}],
                '先找到肩胛控制，再增加重量。', a_done)
            save_submission(pending.id, a_user, pending.exercises, '肩背发力比上次清楚，最后一组稍吃力。', submit=True)
            reviewed = create_plan(b, coach, '呼吸与核心 · 每日练习', timezone.localdate(),
                                   mobility, '配合呼吸，留意腰背位置。', b_done)
            submitted = save_submission(reviewed.id, b_user, mobility, '今天核心控制更稳定，侧支撑完成 25 秒。', submit=True)
            review_submission(submitted.id, coach, '节奏很好。侧支撑先保持身体对齐，再逐步延长时间；不必急着追求更久。')
        self.stdout.write(json.dumps({'created': credentials, 'students': 3,
                                      'sessions': 6}, ensure_ascii=False))
