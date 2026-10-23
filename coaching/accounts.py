from datetime import timedelta
from hashlib import sha256
import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .errors import DomainError
from .models import Invite, Student

def create_student(name):
    name = name.strip()
    if not name or len(name) > 50:
        raise DomainError('学员姓名需为 1–50 个字符')
    return Student.objects.create(name=name)

def issue_invite(student):
    with transaction.atomic():
        student = Student.objects.get(pk=student.pk)
        if student.user_id:
            raise DomainError('该学员已有登录账号')
        student.invites.all().delete()
        token = secrets.token_urlsafe(32)
        Invite.objects.create(student=student, token_hash=sha256(token.encode()).hexdigest(),
                              expires_at=timezone.now() + timedelta(days=7))
        return token

def accept_invite(token, username, password):
    user = get_user_model()(username=username.strip())
    try:
        user.full_clean(exclude=['password'])
        validate_password(password, user)
    except ValidationError as exc:
        raise DomainError('；'.join(exc.messages)) from exc
    user.set_password(password)
    try:
        with transaction.atomic():
            invitation = Invite.objects.filter(token_hash=sha256(token.encode()).hexdigest()).first()
            if not invitation or invitation.used_at or invitation.expires_at <= timezone.now():
                raise DomainError('邀请已失效，请登录已有账号或联系教练')
            if invitation.student.user_id:
                raise DomainError('该学员已完成注册')
            user.save()
            invitation.student.user = user
            invitation.student.save(update_fields=['user'])
            invitation.used_at = timezone.now()
            invitation.save(update_fields=['used_at'])
            return user
    except IntegrityError as exc:
        raise DomainError('账号已存在，请换一个账号') from exc
