import json
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .errors import DomainError
from .models import Kind
from .training import validate_exercises

class LoginForm(AuthenticationForm):
    username = forms.CharField(label='登录账号', widget=forms.TextInput(attrs={'autocomplete': 'username', 'placeholder': '输入你的账号'}))
    password = forms.CharField(label='密码', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'placeholder': '输入密码'}))

class RegisterForm(forms.Form):
    username = forms.CharField(label='设置登录账号', max_length=150)
    password = forms.CharField(label='设置密码', min_length=8, strip=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='再次输入密码', strip=False, widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('password_confirm'):
            self.add_error('password_confirm', '两次输入的密码不一致')
        return data

class StudentForm(forms.Form):
    name = forms.CharField(label='学员姓名', max_length=50, widget=forms.TextInput(attrs={'placeholder': '例如：陈可欣'}))

class SessionForm(forms.Form):
    title = forms.CharField(label='课程名称', max_length=80)
    kind = forms.ChoiceField(label='课程类型', choices=Kind.choices)
    start = forms.DateTimeField(label='开始时间', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    end = forms.DateTimeField(label='结束时间', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    location = forms.CharField(label='上课地点', max_length=120)
    capacity = forms.IntegerField(label='名额', min_value=1, max_value=100, initial=1)

class CreditForm(forms.Form):
    kind = forms.ChoiceField(label='课包类型', choices=Kind.choices)
    units = forms.IntegerField(label='已购买次数', min_value=1, max_value=10000)
    operation_key = forms.UUIDField(widget=forms.HiddenInput)

class ExerciseForm(forms.Form):
    exercises = forms.CharField(widget=forms.HiddenInput)
    note = forms.CharField(label='文字说明', required=False, max_length=4000,
                          widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '写下训练感受或需要留意的地方…'}))

    def clean_exercises(self):
        try:
            return validate_exercises(json.loads(self.cleaned_data['exercises']))
        except (json.JSONDecodeError, DomainError) as exc:
            raise forms.ValidationError(str(exc)) from exc

class PlanForm(ExerciseForm):
    title = forms.CharField(label='计划名称', max_length=80)
    due_date = forms.DateField(label='目标日期', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

class FeedbackForm(forms.Form):
    feedback = forms.CharField(label='给学员的反馈', max_length=4000, widget=forms.Textarea(attrs={'rows': 4, 'placeholder': '肯定进步，再给出一个具体的改进建议。'}))
