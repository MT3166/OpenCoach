import uuid
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

class LessonMigrationTests(TransactionTestCase):
    def test_existing_booking_ledger_and_training_survive_migration(self):
        executor=MigrationExecutor(connection)
        old_target=[('coaching','0001_initial')]
        executor.migrate(old_target)
        try:
            old=executor.loader.project_state(old_target).apps
            Student=old.get_model('coaching','Student')
            Session=old.get_model('coaching','Session')
            Booking=old.get_model('coaching','Booking')
            Credit=old.get_model('coaching','CreditEntry')
            Record=old.get_model('coaching','TrainingRecord')
            student=Student.objects.create(name='迁移学员')
            start=timezone.now()-timedelta(hours=2)
            session=Session.objects.create(title='已有课程',kind='private',start=start,end=start+timedelta(hours=1),location='已有地点',capacity=1)
            item=Booking.objects.create(student=student,session=session,status='completed',operation_key=uuid.uuid4())
            purchased=Credit.objects.create(student=student,kind='private',entry_type='purchase',units=5,operation_key=uuid.uuid4())
            charge=Credit.objects.create(student=student,kind='private',entry_type='consume',units=1,booking=item)
            record=Record.objects.create(booking=item,exercises=[{'name':'划船','weight':'9.5'}],note='已有总结')
            expected=(student.pk,item.pk,purchased.pk,charge.pk,record.pk)
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
        from coaching.models import Student,Booking,CreditEntry,TrainingRecord,DirectLesson
        self.assertEqual(Student.objects.get(pk=expected[0]).name,'迁移学员')
        self.assertEqual(Booking.objects.get(pk=expected[1]).status,'completed')
        self.assertEqual(CreditEntry.objects.get(pk=expected[2]).units,5)
        self.assertIsNone(CreditEntry.objects.get(pk=expected[3]).direct_lesson_id)
        self.assertEqual(TrainingRecord.objects.get(pk=expected[4]).exercises[0]['weight'],'9.5')
        self.assertEqual(DirectLesson.objects.count(),0)
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA foreign_key_check')
            self.assertEqual(cursor.fetchall(),[])
