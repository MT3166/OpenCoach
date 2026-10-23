import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from coaching import booking, lessons
from coaching.errors import DomainError
from coaching.models import Booking, CreditEntry, DirectLesson, Waitlist
from coaching.waitlist import join, promote
from .helpers import make_student, make_session


class StageHardeningTests(TestCase):
    def setUp(self):
        self.coach=get_user_model().objects.create(username='hardening-coach',is_staff=True)
        self.a,self.b=make_student('hardening-a',credits=1),make_student('hardening-b',credits=1)

    def test_reschedule_exact_twelve_hours_and_same_key_wrong_source(self):
        source,target=make_session(30),make_session(40)
        item=booking.reserve(self.a,source.pk,uuid.uuid4())
        key=uuid.uuid4()
        with patch('django.utils.timezone.now',return_value=source.start-timedelta(hours=12)):
            moved=booking.reschedule(item.pk,self.a.user,target.pk,key)
        with self.assertRaises(DomainError):
            booking.reschedule(moved.pk,self.a.user,source.pk,key)

    def test_mixed_old_batch_items_and_later_failure_rolls_back_new_items_only(self):
        old=lessons.record_direct_lesson(self.a,self.coach,'private',timezone.localdate(),'',uuid.uuid4())
        empty=make_student('hardening-empty',credits=0)
        rows=[{'student_id':student.pk,'operation_key':uuid.uuid4()} for student in (self.b,empty)]
        rows.insert(0,{'student_id':self.a.pk,'operation_key':old.operation_key})
        self.client.force_login(self.coach)
        response=self.client.post('/api/v1/coach/lessons/batch/',{'kind':'private','occurred_on':timezone.localdate().isoformat(),'operation_key':str(uuid.uuid4()),'items':[{**row,'operation_key':str(row['operation_key'])} for row in rows]},content_type='application/json')
        self.assertEqual(response.status_code,409)
        self.assertEqual(list(DirectLesson.objects.values_list('pk',flat=True)),[old.pk])
        self.assertEqual(CreditEntry.objects.filter(entry_type='consume').count(),1)

    def test_promoted_exit_rejected_and_monthly_count_survives_booking_cancel(self):
        source=make_session()
        old=booking.reserve(self.a,source.pk,uuid.uuid4())
        queued=join(self.b,source.pk,uuid.uuid4())
        booking.cancel(old.pk,self.coach)
        queued.refresh_from_db()
        self.client.force_login(self.b.user)
        response=self.client.post(f'/api/v1/student/waitlist/{queued.pk}/leave/')
        self.assertEqual(response.status_code,409)
        booking.cancel(queued.booking_id,self.coach)
        self.client.force_login(self.coach)
        response=self.client.get('/api/v1/coach/reports/monthly/',{'month':timezone.localdate().strftime('%Y-%m')})
        self.assertEqual(response.json()['data']['waitlist_promoted'],1)

    def test_promotion_operation_collision_skips_without_breaking_release(self):
        from uuid import uuid5,NAMESPACE_URL
        source=make_session()
        old=booking.reserve(self.a,source.pk,uuid.uuid4())
        queued=join(self.b,source.pk,uuid.uuid4())
        collision=uuid5(NAMESPACE_URL,f'opencoach.waitlist:{queued.pk}:{queued.operation_key}')
        booking.reserve(make_student('hardening-collision'),make_session(40).pk,collision)
        booking.cancel(old.pk,self.coach)
        self.assertFalse(Booking.objects.filter(student=self.b).exists())
        queued.refresh_from_db()
        self.assertEqual(queued.status,'waiting')

    def test_future_batch_invalid_nested_and_strict_integer_are_errors(self):
        self.client.force_login(self.coach)
        payload={'kind':'private','occurred_on':(timezone.localdate()+timedelta(days=1)).isoformat(),'operation_key':str(uuid.uuid4()),'items':[{'student_id':True,'operation_key':str(uuid.uuid4()),'exercises':'bad'}]}
        response=self.client.post('/api/v1/coach/lessons/batch/',payload,content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertIn('error',response.json())
        self.assertEqual(DirectLesson.objects.count(),0)


class StageMigrationTests(TransactionTestCase):
    def test_v2_ledger_upgrades_permanently_without_mutating_history(self):
        executor=MigrationExecutor(connection)
        target=[('coaching','0002_direct_lesson')]
        executor.migrate(target)
        try:
            apps=executor.loader.project_state(target).apps
            Student,Session,BookingV2,Credit=[apps.get_model('coaching',name) for name in ('Student','Session','Booking','CreditEntry')]
            student=Student.objects.create(name='升级验证')
            course=Session.objects.create(title='旧预约',kind='private',start=timezone.now()-timedelta(hours=2),end=timezone.now()-timedelta(hours=1),location='教室',capacity=1)
            item=BookingV2.objects.create(student=student,session=course,status='completed',operation_key=uuid.uuid4())
            purchase=Credit.objects.create(student=student,kind='private',entry_type='purchase',units=5,operation_key=uuid.uuid4())
            charge=Credit.objects.create(student=student,kind='private',entry_type='consume',units=1,booking=item)
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
        from coaching.api.serializers import wallets
        from coaching.models import Student as CurrentStudent
        wallet=wallets(CurrentStudent.objects.get(pk=student.pk))[0]
        self.assertEqual((wallet['remaining'],wallet['available'],wallet['expired']),(4,4,0))
        self.assertIsNone(CreditEntry.objects.get(pk=purchase.pk).expires_on)
        self.assertEqual(CreditEntry.objects.get(pk=charge.pk).booking_id,item.pk)
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA foreign_key_check')
            self.assertEqual(cursor.fetchall(),[])


class StageConcurrencyTests(TransactionTestCase):
    def race(self,actions):
        gate=Barrier(2)
        def run(action):
            close_old_connections()
            try:
                connection.ensure_connection()
                gate.wait(timeout=10)
                try:
                    action()
                    return True
                except DomainError:
                    return False
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run,actions))

    def test_two_releases_compete_for_same_waiter_last_credit(self):
        coach=get_user_model().objects.create(username='race-hardening',is_staff=True)
        waiter=make_student('race-last-waiter',credits=1)
        a,b=make_student('race-occupant-a'),make_student('race-occupant-b')
        first,second=make_session(30),make_session(40)
        booked_a,booked_b=booking.reserve(a,first.pk,uuid.uuid4()),booking.reserve(b,second.pk,uuid.uuid4())
        join(waiter,first.pk,uuid.uuid4());join(waiter,second.pk,uuid.uuid4())
        self.assertEqual(self.race([lambda:booking.cancel(booked_a.pk,coach),lambda:booking.cancel(booked_b.pk,coach)]),[True,True])
        self.assertEqual(Booking.objects.filter(student=waiter,status='booked').count(),1)
        self.assertEqual(Waitlist.objects.filter(student=waiter,status='promoted').count(),1)
        self.assertEqual(booking.balances(waiter,'private')['available'],0)

    def test_duplicate_batch_concurrent_consumes_once(self):
        coach=get_user_model().objects.create(username='race-batch',is_staff=True)
        student=make_student('race-batch-student',credits=1)
        key=uuid.uuid4();rows=[{'student_id':student.pk,'operation_key':uuid.uuid4()}]
        action=lambda:lessons.record_batch(coach,'private',timezone.localdate(),key,rows)
        self.assertEqual(self.race([action,action]),[True,True])
        self.assertEqual(DirectLesson.objects.count(),1)
        self.assertEqual(CreditEntry.objects.filter(entry_type='consume').count(),1)
