import logging
from datetime import date
from django.core.exceptions import PermissionDenied
from django.db import OperationalError
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.views.csrf import csrf_failure as html_csrf_failure
from django.views.decorators.csrf import csrf_protect
from rest_framework import exceptions, serializers
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView, exception_handler
from coaching.errors import DomainError
from coaching.models import Student

def success(data, status=200):
    return Response({'data': data}, status=status)

def error(code, message, status, fields=None):
    payload = {'code': code, 'message': message}
    if fields:
        payload['fields'] = fields
    return Response({'error': payload}, status=status)

def csrf_failure(request, reason=''):
    if request.path.startswith('/api/'):
        return JsonResponse({'error': {'code':'csrf_failed','message':'登录信息已更新，请刷新页面后重新提交。'}}, status=403)
    return html_csrf_failure(request, reason=reason)

def api_not_found(request, **kwargs):
    return JsonResponse({'error':{'code':'not_found','message':'接口不存在'}}, status=404)

def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return error('domain_conflict', str(exc), 409)
    if isinstance(exc, OperationalError) and 'locked' in str(exc).lower():
        return error('temporarily_unavailable','系统繁忙，请保留当前操作稍后重试。',503)
    if isinstance(exc, (Http404, exceptions.NotFound)):
        return error('not_found','记录不存在或不可访问',404)
    if isinstance(exc, (PermissionDenied, exceptions.PermissionDenied)):
        return error('forbidden','当前账号不能执行此操作',403)
    if isinstance(exc, exceptions.NotAuthenticated):
        return error('unauthenticated','请先登录',401)
    if isinstance(exc, exceptions.ValidationError):
        fields = exc.detail if isinstance(exc.detail, dict) else {'non_field_errors': exc.detail}
        return error('validation_error','请检查填写内容',400,fields)
    response = exception_handler(exc, context)
    if response:
        codes = {400:'invalid_json',405:'method_not_allowed',415:'unsupported_media_type'}
        return error(codes.get(response.status_code,'request_failed'),str(getattr(exc,'detail','请求失败')),response.status_code)
    logging.getLogger(__name__).exception('API request failed', exc_info=exc)
    return error('internal_error','暂时无法完成，请稍后重试。',500)

class IsCoach(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_active and request.user.is_staff)

class IsStudent(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_staff or not request.user.is_active:
            return False
        student = Student.objects.filter(user=request.user).first()
        if student is None:
            return False
        request.student = student
        return True

@method_decorator(csrf_protect, name='dispatch')
class ProtectedAPIView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        result = super().finalize_response(request,response,*args,**kwargs)
        result['Cache-Control'] = 'no-store'
        return result

class CoachView(ProtectedAPIView):
    permission_classes = [IsAuthenticated, IsCoach]

class StudentView(ProtectedAPIView):
    permission_classes = [IsAuthenticated, IsStudent]

class InputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            extra = set(data) - set(self.fields)
            if extra:
                raise serializers.ValidationError({key:['不支持此字段'] for key in sorted(extra)})
        return super().to_internal_value(data)

class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, value):
        if type(value) is not int:
            raise serializers.ValidationError('请填写整数')
        return super().to_internal_value(value)

def validated(serializer_class, request):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data

def query_int(request, name, default=None, minimum=1, maximum=None):
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        if value < minimum or (maximum is not None and value > maximum):
            raise ValueError
    except (ValueError, TypeError):
        raise exceptions.ValidationError({name:['请选择有效数字']})
    return value

def query_day(request):
    raw = request.query_params.get('day')
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise exceptions.ValidationError({'day':['请使用 YYYY-MM-DD 日期']})

def query_choice(request, name, choices):
    raw = request.query_params.get(name)
    if raw and raw not in choices:
        raise exceptions.ValidationError({name:['请选择有效选项']})
    return raw

def paginate(request, queryset, serialize):
    page = query_int(request,'page',1)
    size = query_int(request,'page_size',30,maximum=100)
    total = queryset.count()
    return {'items':[serialize(item) for item in queryset[(page-1)*size:page*size]],
            'pagination':{'page':page,'page_size':size,'total':total}}
