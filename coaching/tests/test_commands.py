import io
import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase
from coaching.models import Booking, CreditEntry, Student

class CommandTests(TransactionTestCase):
    def test_seed_creates_real_accounts_and_bookings(self):
        call_command('seed_demo', stdout=io.StringIO())
        self.assertTrue(get_user_model().objects.filter(username='coach', is_staff=True).exists())
        self.assertGreater(Booking.objects.count(), 0)
        self.assertTrue(Student.objects.filter(user__username='xiaoyu').exists())

    def test_repeated_seed_keeps_existing_password_and_balances(self):
        call_command('seed_demo', stdout=io.StringIO())
        coach = get_user_model().objects.filter(username='coach').first()
        self.assertIsNotNone(coach)
        password = coach.password
        counts = (Booking.objects.count(), CreditEntry.objects.count())
        call_command('seed_demo', stdout=io.StringIO())
        coach.refresh_from_db()
        self.assertEqual(coach.password, password)
        self.assertEqual((Booking.objects.count(), CreditEntry.objects.count()), counts)

    def test_backup_contains_committed_records(self):
        Student.objects.create(name='备份中的学员')
        with tempfile.TemporaryDirectory(prefix='opencoach-backup-') as temporary:
            path = Path(temporary) / 'snapshot.sqlite3'
            call_command('backup_db', output=str(path), stdout=io.StringIO())
            self.assertTrue(path.exists())
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT name FROM coaching_student').fetchone()[0], '备份中的学员')
