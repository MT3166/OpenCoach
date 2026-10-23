"""在测试站点通过真实 HTTP 表单验收，密码仅从隐藏输入读取。"""
import argparse
from datetime import date, timedelta
import getpass
import http.cookiejar
from html.parser import HTMLParser
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid

class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms, self.current, self.readonly = [], None, []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {}
            self.forms.append(self.current)
        if tag == 'input':
            if self.current is not None and attrs.get('name'):
                self.current[attrs['name']] = attrs.get('value', '')
            if 'readonly' in attrs:
                self.readonly.append(attrs.get('value', ''))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None

class Browser:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self.cookies))

    def send(self, path, data=None, expected=200):
        url = path if path.startswith('http') else self.base + path
        request = urllib.request.Request(url,
            data=urllib.parse.urlencode(data).encode() if data is not None else None,
            headers={'Referer': url, 'Origin': self.base})
        try:
            response = self.opener.open(request, timeout=25)
        except urllib.error.HTTPError as exc:
            response = exc
        if response.status != expected:
            raise RuntimeError(f'{path}: expected {expected}, got {response.status}')
        return response.geturl(), response.read().decode('utf-8')

    def get(self, path, expected=200):
        return self.send(path, expected=expected)[1]

    def post(self, path, data, csrf_path=None):
        html = self.get(csrf_path or path)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
        return self.send(path, {**data, 'csrfmiddlewaretoken': token})

    def login(self, username, password):
        url, _ = self.post('/login/', {'username': username, 'password': password})
        if '/login/' in url:
            raise RuntimeError('测试账号登录失败：' + username)

def wallet(html):
    available = [int(x) for x in re.findall(r'class="wallet-number">\s*(\d+)', html)]
    remaining = [int(x) for x in re.findall(r'剩余 (\d+) 次', html)]
    reserved = [int(x) for x in re.findall(r'已约 (\d+) 次', html)]
    return list(zip(remaining, reserved, available))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='https://coach.qtedu.ac.cn')
    args = parser.parse_args()
    coach, student, other = [Browser(args.base) for _ in range(3)]
    for browser, username in [(coach, 'coach'), (student, 'xiaoyu'), (other, 'achen')]:
        password = getpass.getpass(username + ' password (not saved): ')
        browser.login(username, password)
        del password
    print('real_http_logins=PASS', flush=True)
    student.get('/coach/', expected=403)
    other.get('/student/plans/1/', expected=404)

    _, html = coach.post('/coach/students/3/', {'action': 'invite'})
    invitation = next(value for value in Forms(html).readonly if '/invite/' in value)
    newcomer = Browser(args.base)
    new_password = secrets.token_urlsafe(12)
    url, _ = newcomer.post(invitation, {'username': 'yinuo', 'password': new_password,
                                      'password_confirm': new_password})
    assert '/student/' in url
    purchase_key = str(uuid.uuid4())
    payload = {'action': 'credit', 'kind': 'private', 'units': '3', 'operation_key': purchase_key}
    coach.post('/coach/students/3/', payload)
    _, html = coach.post('/coach/students/3/', payload)
    assert wallet(html)[0] == (3, 0, 3)
    print('invitation_and_purchase_retry=PASS', flush=True)

    forms = Forms(student.get('/student/sessions/')).forms
    private = next(form for form in forms if form.get('session_id') == '2')
    student.post('/student/sessions/', private)
    student.post('/student/sessions/', private)
    course_html = coach.get('/coach/sessions/2/')
    private_ids = set(re.findall(r'/coach/bookings/(\d+)/', course_html))
    assert len(private_ids) == 1
    private_id = next(iter(private_ids))
    assert wallet(student.get('/student/profile/'))[0] == (11, 2, 9)
    before = set(re.findall(r'/coach/bookings/(\d+)/', coach.get('/coach/sessions/4/')))
    group = next(form for form in forms if form.get('session_id') == '4')
    student.post('/student/sessions/', group)
    after = set(re.findall(r'/coach/bookings/(\d+)/', coach.get('/coach/sessions/4/')))
    group_id = next(iter(after - before))
    assert wallet(student.get('/student/profile/'))[1] == (8, 1, 7)
    student.post(f'/student/bookings/{group_id}/cancel/', {}, csrf_path='/student/bookings/')
    student.post(f'/student/bookings/{group_id}/cancel/', {}, csrf_path='/student/bookings/')
    assert wallet(student.get('/student/profile/'))[1] == (8, 0, 8)
    print('reservation_retry_and_group_cancellation=PASS', flush=True)

    coach.post('/coach/bookings/1/', {'action': 'finish', 'outcome': 'completed'})
    coach.post('/coach/bookings/1/', {'action': 'finish', 'outcome': 'completed'})
    assert wallet(student.get('/student/profile/'))[0] == (10, 1, 9)
    rows = [{'name': '高脚杯深蹲', 'sets': 3, 'reps': 10, 'weight': '9.5', 'duration': None}]
    note = '控制下降速度，重心更稳定。'
    coach.post('/coach/bookings/1/', {'action': 'record', 'exercises': json.dumps(rows), 'note': note})
    assert note in student.get('/student/bookings/')
    url, _ = coach.post('/coach/bookings/1/', {'action': 'plan', 'title': '动作巩固 · 课后练习',
        'due_date': (date.today() + timedelta(days=1)).isoformat(), 'exercises': json.dumps(rows),
        'note': '保持稳定呼吸，记录实际完成数据。'})
    plan_id = re.search(r'/coach/plans/(\d+)/', url).group(1)
    student.post(f'/student/plans/{plan_id}/', {'exercises': json.dumps(rows),
        'note': '三组完成，下降更稳定。', 'intent': 'submit'})
    feedback = '动作控制有进步。保持同样重量，下降放慢到两秒，每组之间充分休息。'
    coach.post(f'/coach/plans/{plan_id}/', {'feedback': feedback})
    assert feedback in student.get(f'/student/plans/{plan_id}/')
    other.get(f'/student/plans/{plan_id}/', expected=404)
    print('completion_record_plan_submission_feedback=PASS', flush=True)
    print('cross_student_object_permissions=PASS', flush=True)
    print('NEW_ACCOUNT yinuo ' + new_password, flush=True)
    print(json.dumps({'private_booking': int(private_id), 'cancelled_group_booking': int(group_id),
                      'plan': int(plan_id), 'private_wallet': [10, 1, 9], 'group_wallet': [8, 0, 8]}), flush=True)

if __name__ == '__main__':
    main()
