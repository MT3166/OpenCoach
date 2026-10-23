"""在测试域名验证真实H5/API流程；仅为明确命名的验收学员创建数据。密码只在内存。"""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
import http.cookiejar
import json
import re
import secrets
import time
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
import urllib.error
import urllib.request
import uuid

class Browser:
    def __init__(self, base, origin_ip=None):
        self.base=base.rstrip('/')
        self.origin_ip=origin_ip
        self.curl=shutil.which('curl.exe') or shutil.which('curl')
        self.temporary=tempfile.TemporaryDirectory(prefix='opencoach-http-') if self.curl else None
        if self.temporary:
            assert Path(self.temporary.name).resolve().parent==Path(tempfile.gettempdir()).resolve()
        self.cookie_file=Path(self.temporary.name)/'cookies.txt' if self.temporary else None
        self.jar=http.cookiejar.MozillaCookieJar(str(self.cookie_file)) if self.cookie_file else http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf=''

    def call(self, path, payload=None, method='GET', expected=(200,)):
        body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
        headers={'Accept':'application/json'}
        if method not in ['GET','HEAD']:
            headers.update({'Content-Type':'application/json','X-CSRFToken':self.csrf,'Origin':self.base,'Referer':self.base+'/login/'})
        if self.curl:
            command=[self.curl,'--silent','--show-error','--noproxy','*','--max-time','25','--request',method,
                     '--cookie',str(self.cookie_file),'--cookie-jar',str(self.cookie_file),'--write-out','\n%{http_code}']
            if self.origin_ip:
                parsed=urlsplit(self.base)
                command+=['--resolve',f'{parsed.hostname}:{parsed.port or 443}:{self.origin_ip}']
            for key,value in headers.items():
                command+=['--header',key+': '+value]
            if body is not None:
                command+=['--data-binary','@-']
            command.append(self.base+path)
            result=subprocess.run(command,input=body,capture_output=True,timeout=30)
            if result.returncode:
                raise RuntimeError('HTTPS连接未完成：'+result.stderr.decode('utf-8','replace')[:200])
            raw,status=result.stdout.rsplit(b'\n',1)
            data=json.loads(raw)
            status=int(status)
            if status not in expected:
                raise RuntimeError(f'{method} {path}: status {status}, '+str(data.get('error',{}).get('message','unexpected response')))
            self.jar.load(ignore_discard=True,ignore_expires=True)
            value=data.get('data',data)
            if isinstance(value,dict) and 'csrf_token' in value:
                self.csrf=value['csrf_token']
            return value
        request=urllib.request.Request(self.base+path,data=body,headers=headers,method=method)
        try:
            response=self.opener.open(request,timeout=25)
        except urllib.error.HTTPError as exc:
            response=exc
        with response:
            data=json.loads(response.read())
            if response.status not in expected:
                raise RuntimeError(f'{method} {path}: status {response.status}, '+str(data.get('error',{}).get('message','unexpected response')))
            result=data.get('data',data)
            if isinstance(result,dict) and 'csrf_token' in result:
                self.csrf=result['csrf_token']
            return result

    def login(self, username, password):
        self.call('/api/v1/session/')
        return self.call('/api/v1/auth/login/',{'username':username,'password':password},'POST')

    def post(self, path, data, expected=(200,)):
        return self.call('/api/v1/'+path,data,'POST',expected)

    def get(self, path, expected=(200,)):
        return self.call('/api/v1/'+path,expected=expected)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='https://coach.qtedu.ac.cn')
    parser.add_argument('--coach',default='coach')
    parser.add_argument('--student',default='xiaoyu')
    parser.add_argument('--origin-ip',help='指定测试服务器的HTTPS地址，保留域名与证书验证')
    args=parser.parse_args()
    if not args.base.startswith('https://'):
        raise RuntimeError('公网验收必须使用HTTPS')
    coach_password=getpass.getpass('Coach password (not saved): ')
    student_password=getpass.getpass('Student password (not saved): ')
    coach,existing,child=Browser(args.base,args.origin_ip),Browser(args.base,args.origin_ip),Browser(args.base,args.origin_ip)
    assert coach.login(args.coach,coach_password)['user']['role']=='coach'
    assert existing.login(args.student,student_password)['user']['role']=='student'
    del coach_password,student_password
    assert any(cookie.secure and any(key.lower()=='httponly' for key in cookie._rest) for cookie in coach.jar if cookie.name.startswith('oc_session_'))
    original_wallet=existing.get('student/profile/')['wallets']
    existing.get('coach/dashboard/',expected=(403,))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    student=coach.post('coach/students/',{'name':'发布验收学员 '+stamp},(201,))
    sid=student['id']
    private_key=str(uuid.uuid4())
    purchase={'kind':'private','units':5,'operation_key':private_key}
    coach.post(f'coach/students/{sid}/credits/',purchase,(201,))
    coach.post(f'coach/students/{sid}/credits/',purchase)
    coach.post(f'coach/students/{sid}/credits/',{'kind':'group','units':3,'operation_key':str(uuid.uuid4())},(201,))
    local_day=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    payload={'student_id':sid,'kind':'private','occurred_on':local_day,'note':'发布验收：直接记课','operation_key':str(uuid.uuid4())}
    first=coach.post('coach/lessons/',payload,(201,))
    retry=coach.post('coach/lessons/',payload)
    lid=first['lesson']['id']
    assert retry['lesson']['id']==lid
    assert next(item for item in retry['wallets'] if item['kind']=='private')['remaining']==4
    coach.call(f'/api/v1/coach/lessons/{lid}/',{'note':'发布验收：补写总结，未重复扣课'},'PATCH')
    payload['operation_key']=str(uuid.uuid4())
    coach.post('coach/lessons/',payload,(201,))
    assert next(item for item in coach.get(f'coach/students/{sid}/')['wallets'] if item['kind']=='private')['remaining']==3
    invitation=coach.post(f'coach/students/{sid}/invitations/',{},(201,))
    token=invitation['url'].rstrip('/').rsplit('/',1)[1]
    child.get('session/')
    child.get(f'invitations/{token}/')
    secret='Aq!'+secrets.token_urlsafe(20)
    child.post(f'invitations/{token}/accept/',{'username':'acceptance-'+stamp,'password':secret,'password_confirm':secret},(201,))
    del secret
    assert len(child.get('student/lessons/')['items'])==2
    existing.get(f'student/lessons/{lid}/',expected=(404,))
    sessions=coach.get('coach/sessions/?page_size=100')['items']
    def course(start, minutes=30):
        while any(not row['cancelled'] and datetime.fromisoformat(row['start'])<start+timedelta(minutes=minutes) and datetime.fromisoformat(row['end'])>start for row in sessions):
            start+=timedelta(hours=2)
        result=coach.post('coach/sessions/',{'title':'发布验收私教 '+stamp,'kind':'private','start':start.isoformat(),'end':(start+timedelta(minutes=minutes)).isoformat(),'location':'发布验收测试课程','capacity':1},(201,))
        sessions.append(result)
        return result
    far=course(datetime.now(timezone.utc)+timedelta(days=3))
    reservation={'session_id':far['id'],'operation_key':str(uuid.uuid4())}
    booked=child.post('student/bookings/',reservation,(201,))
    assert child.post('student/bookings/',reservation)['id']==booked['id']
    child.post(f'student/bookings/{booked["id"]}/cancel/',{})
    reservation['operation_key']=str(uuid.uuid4())
    rebooked=child.post('student/bookings/',reservation,(201,))
    child.post(f'student/bookings/{booked["id"]}/cancel/',{})
    assert any(item['id']==rebooked['id'] and item['status']=='booked' for item in child.get('student/bookings/')['items'])
    coach.post(f'coach/bookings/{rebooked["id"]}/cancel/',{})
    near_start=datetime.now(timezone.utc)+timedelta(seconds=20)
    if any(not row['cancelled'] and datetime.fromisoformat(row['start'])<near_start+timedelta(minutes=2) and datetime.fromisoformat(row['end'])>near_start for row in sessions):
        raise RuntimeError('当前有课程时间冲突；保留已创建验收数据，选独立时间完成预约流程验收')
    near=course(near_start,minutes=2)
    item=child.post('student/bookings/',{'session_id':near['id'],'operation_key':str(uuid.uuid4())},(201,))
    wait=max(0,(datetime.fromisoformat(near['start'])-datetime.now(timezone.utc)).total_seconds()+1)
    if wait>25:
        raise RuntimeError('验收课程开始时间超出短等待范围')
    print('direct_recording_invitation_reservation_cancellation=PASS',flush=True)
    time.sleep(wait)
    coach.post(f'coach/bookings/{item["id"]}/finish/',{'outcome':'completed'})
    coach.post(f'coach/bookings/{item["id"]}/finish/',{'outcome':'completed'})
    coach.call(f'/api/v1/coach/bookings/{item["id"]}/record/',{'note':'发布验收：预约课文字记录','exercises':[]},'PUT')
    plan=coach.post('coach/plans/',{'student_id':sid,'booking_id':item['id'],'title':'发布验收练习','due_date':local_day,'exercises':[{'name':'划船','reps':12}],'note':'发布验收用'},(201,))
    body={'exercises':[{'name':'划船','reps':12,'weight':'9.5'}],'note':'发布验收实际完成','intent':'draft'}
    child.call(f'/api/v1/student/plans/{plan["id"]}/submission/',body,'PUT')
    body['intent']='submit'
    submission=child.call(f'/api/v1/student/plans/{plan["id"]}/submission/',body,'PUT')
    child.call(f'/api/v1/student/plans/{plan["id"]}/submission/',body,'PUT')
    feedback='发布验收通过：继续保持动作控制。'
    coach.call(f'/api/v1/coach/submissions/{submission["id"]}/feedback/',{'feedback':feedback},'PUT')
    assert child.get(f'student/plans/{plan["id"]}/')['submission']['feedback']==feedback
    assert child.get('student/lessons/')['pagination']['total']==3
    assert next(row for row in child.get('student/profile/')['wallets'] if row['kind']=='private')['remaining']==2
    assert existing.get('student/profile/')['wallets']==original_wallet
    print('appointment_completion_note_plan_submission_feedback=PASS',flush=True)
    print('existing_student_wallet_unchanged=PASS',flush=True)
    print('ACCEPTANCE='+json.dumps({'student_id':sid,'direct_lesson_id':lid,'session_ids':[far['id'],near['id']],'booking_ids':[booked['id'],rebooked['id'],item['id']],'plan_id':plan['id']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
