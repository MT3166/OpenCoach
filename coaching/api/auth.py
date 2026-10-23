from hashlib import sha256
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from coaching import accounts
from coaching.models import Invite, Student
from .common import ProtectedAPIView, InputSerializer, validated, success, error

def session_data(request):
    name = settings.BRAND_NAME.strip()
    brand = {'display_name':name if name and name != 'OpenCoach' else settings.COACH_NAME,
             'coach_name':settings.COACH_NAME}
    user = request.user
    identity = None
    if user.is_authenticated and user.is_active:
        student = Student.objects.filter(user=user).first() if not user.is_staff else None
        if user.is_staff or student:
            identity = {'id':user.id,'username':user.username,'role':'coach' if user.is_staff else 'student',
                        'display_name':settings.COACH_NAME if user.is_staff else student.name}
    return {'user':identity,'brand':brand,'csrf_token':get_token(request)}

class LoginInput(InputSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False)

class RegisterInput(LoginInput):
    password_confirm = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm':['两次输入的密码不一致']})
        try:
            from django.contrib.auth import get_user_model
            validate_password(attrs['password'],get_user_model()(username=attrs['username']))
        except ValidationError as exc:
            raise serializers.ValidationError({'password':exc.messages}) from exc
        return attrs

class SessionView(ProtectedAPIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return success(session_data(request))

class LoginView(ProtectedAPIView):
    permission_classes = [AllowAny]
    def post(self, request):
        if request.user.is_authenticated:
            return error('domain_conflict','请先退出当前账号再登录其他账号',409)
        data = validated(LoginInput,request)
        user = authenticate(request, **data)
        if not user or (not user.is_staff and not Student.objects.filter(user=user).exists()):
            return error('invalid_credentials','账号或密码不正确',401)
        login(request,user)
        request.user = user
        return success(session_data(request))

class LogoutView(ProtectedAPIView):
    permission_classes = [AllowAny]
    def post(self, request):
        logout(request)
        return success(session_data(request))

def invitation(token):
    item = Invite.objects.select_related('student').filter(token_hash=sha256(token.encode()).hexdigest()).first()
    if not item or item.used_at or item.expires_at <= timezone.now() or item.student.user_id:
        return None
    return item

class InvitationView(ProtectedAPIView):
    permission_classes = [AllowAny]
    def get(self, request, token):
        item = invitation(token)
        if not item:
            return error('invitation_invalid','邀请已失效，请联系教练或登录已有账号',409)
        return success({'student_name':item.student.name,'expires_at':item.expires_at.isoformat()})

class AcceptInvitationView(ProtectedAPIView):
    permission_classes = [AllowAny]
    def post(self, request, token):
        if request.user.is_authenticated:
            return error('domain_conflict','请先退出当前账号再接受邀请',409)
        if not invitation(token):
            return error('invitation_invalid','邀请已失效，请联系教练',409)
        data = validated(RegisterInput,request)
        user = accounts.accept_invite(token,data['username'],data['password'])
        login(request,user,backend='django.contrib.auth.backends.ModelBackend')
        request.user = user
        return success(session_data(request),201)
