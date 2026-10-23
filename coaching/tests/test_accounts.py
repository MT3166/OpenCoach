from datetime import timedelta
from hashlib import sha256
from django.test import TestCase
from django.utils import timezone
from coaching.accounts import accept_invite, create_student, issue_invite
from coaching.errors import DomainError
from coaching.models import Invite, Student

class AccountTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(name='小雨')
        self.token = 'an-independent-test-invitation-token'
        self.invite = Invite.objects.create(student=self.student,
            token_hash=sha256(self.token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(days=1))

    def test_registration_binds_student(self):
        user = accept_invite(self.token, 'xiaoyu', 'Exercise-74!')
        self.assertIsNotNone(user)
        self.student.refresh_from_db()
        self.assertEqual(self.student.user_id, user.id)
        self.assertTrue(user.check_password('Exercise-74!'))
        self.assertFalse(user.is_staff)

    def test_used_invitation_cannot_create_second_user(self):
        self.invite.used_at = timezone.now()
        self.invite.save()
        with self.assertRaises(DomainError):
            accept_invite(self.token, 'second', 'Exercise-74!')

    def test_expired_invitation_rejected(self):
        self.invite.expires_at = timezone.now() - timedelta(seconds=1)
        self.invite.save()
        with self.assertRaises(DomainError):
            accept_invite(self.token, 'expired', 'Exercise-74!')

    def test_reissuing_removes_old_invitation(self):
        issue_invite(self.student)
        self.assertFalse(Invite.objects.filter(pk=self.invite.pk).exists())

    def test_empty_student_name_rejected(self):
        with self.assertRaises(DomainError):
            create_student('  ')

    def test_student_name_persisted(self):
        result = create_student(' 阿辰 ')
        self.assertIsNotNone(result)
        self.assertEqual(result.name, '阿辰')

    def test_weak_password_rejected(self):
        with self.assertRaises(DomainError):
            accept_invite(self.token, 'weak', '123')
