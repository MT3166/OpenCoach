"""Local real-browser acceptance using disposable data, installed Chrome and stdlib.

Run with the project's Python after `npm --prefix frontend run build`.
Never reads the instance database or credentials; never connects to a remote host.
"""
import base64
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

from preview import CDP
from smoke_h5 import Browser

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'artifacts' / 'five-stages'


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def until(check, description):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (OSError, KeyError, ValueError):
            pass
        time.sleep(.1)
    raise RuntimeError('Timeout: ' + description)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='five-stages-') as temporary:
        env = {**os.environ, 'OPENCOACH_DATA_DIR':temporary, 'OPENCOACH_FRONTEND_ENABLED':'1',
               'DJANGO_DEBUG':'1', 'DJANGO_ALLOWED_HOSTS':'127.0.0.1,localhost',
               'DJANGO_SETTINGS_MODULE':'opencoach.settings', 'DJANGO_SECRET_KEY':secrets.token_urlsafe(48)}
        os.environ.update({key:env[key] for key in ('OPENCOACH_DATA_DIR','OPENCOACH_FRONTEND_ENABLED',
            'DJANGO_DEBUG','DJANGO_ALLOWED_HOSTS','DJANGO_SETTINGS_MODULE','DJANGO_SECRET_KEY')})
        subprocess.run([sys.executable,'manage.py','migrate','--noinput'],cwd=ROOT,env=env,check=True,capture_output=True)
        sys.path.insert(0,str(ROOT))
        import django
        django.setup()
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from coaching.models import Student, Session, DirectLesson
        from coaching import booking
        password=secrets.token_urlsafe(24)
        coach=get_user_model().objects.create_user('browser-coach',password=password,is_staff=True)
        students=[]
        for name in ('browser-a','browser-b','browser-waiter'):
            user=get_user_model().objects.create_user(name,password=password)
            student=Student.objects.create(name=name,user=user)
            booking.add_credit(student,'group',4,uuid.uuid4(),expires_on=timezone.localdate()+timedelta(days=3))
            students.append(student)
        start=timezone.now()+timedelta(hours=40)
        course=Session.objects.create(title='满员小班验收',kind='group',start=start,end=start+timedelta(hours=1),location='验收教室',capacity=2)
        target=Session.objects.create(title='改期目标小班',kind='group',start=start+timedelta(hours=3),end=start+timedelta(hours=4),location='验收教室',capacity=2)
        original=booking.reserve(students[0],course.pk,uuid.uuid4())
        booking.reserve(students[1],course.pk,uuid.uuid4())
        server_port,chrome_port=port(),port()
        origin=f'http://127.0.0.1:{server_port}'
        process=subprocess.Popen([sys.executable,'manage.py','runserver',f'127.0.0.1:{server_port}','--noreload'],cwd=ROOT,env=env,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        browser_process=None;cdp=None
        try:
            until(lambda:urllib.request.urlopen(origin+'/api/v1/session/',timeout=1).status==200,'Django server')
            chrome=Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
            browser_process=subprocess.Popen([str(chrome),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--disable-background-networking','--no-proxy-server',f'--user-data-dir={temporary}/chrome',
                '--remote-debugging-address=127.0.0.1',f'--remote-debugging-port={chrome_port}','about:blank'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            targets=until(lambda:json.load(urllib.request.urlopen(f'http://127.0.0.1:{chrome_port}/json/list',timeout=1)),'Chrome')
            cdp=CDP(next(item['webSocketDebuggerUrl'] for item in targets if item['type']=='page'))
            cdp.call('Page.enable');cdp.call('Network.enable')
            def js(expression):
                result=cdp.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in result:
                    raise RuntimeError(str(result['exceptionDetails']))
                return result.get('result',{}).get('value')
            def wait(expression):
                return until(lambda:js(expression),expression)
            def navigate(path,heading):
                cdp.call('Page.navigate',{'url':origin+path})
                wait('document.querySelector("h1")?.textContent.includes('+json.dumps(heading)+') && !document.querySelector(".loading")')
            def login(name):
                client=Browser(origin)
                client.login(name,password)
                cdp.call('Network.clearBrowserCookies')
                for cookie in client.jar:
                    cdp.call('Network.setCookie',{'name':cookie.name,'value':cookie.value,'url':origin,'path':'/'})
            def click(text):
                js('(()=>{const el=[...document.querySelectorAll("button,a,summary")].find(el=>el.textContent.trim()==='+json.dumps(text)+');if(!el)throw Error("Missing control");el.click()})()')
            def input_value(selector,value):
                js('(()=>{const el=document.querySelector('+json.dumps(selector)+');if(!el)throw Error("Missing input");el.value='+json.dumps(value)+';el.dispatchEvent(new Event("input",{bubbles:true}));el.dispatchEvent(new Event("change",{bubbles:true}))})()')
            def screenshot(name,width=390,height=844):
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<600})
                wait('document.documentElement.scrollWidth<=innerWidth')
                data=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False,'clip':{'x':0,'y':0,'width':width,'height':height,'scale':1}})
                (OUTPUT/name).write_bytes(base64.b64decode(data['data']))
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            login('browser-waiter')
            navigate('/student/sessions/','约一节课')
            wait('[...document.querySelectorAll("button")].some(el=>el.textContent.trim()==="加入候补")')
            click('加入候补')
            wait('document.body.textContent.includes("已加入候补")')
            navigate('/student/bookings/','我的预约')
            wait('document.body.textContent.includes("候补第 1 位")')
            screenshot('student-waitlist-mobile.png')
            login('browser-coach')
            navigate(f'/coach/bookings/{original.pk}/','这节课')
            click('取消这笔预约');click('确认取消')
            wait('document.body.textContent.includes("预约已取消")')
            navigate(f'/coach/sessions/{course.pk}/','满员小班验收')
            wait('document.body.textContent.includes("已递补为正式预约")')
            screenshot('coach-queue-desktop.png',1280,960)
            login('browser-waiter')
            navigate('/student/bookings/','我的预约')
            click('改期到其他课次')
            wait('document.querySelector('+json.dumps(f'select option[value="{target.pk}"]')+')')
            input_value('select',str(target.pk))
            # Changing filters must clear stale selections before submission.
            input_value('input[type=date]',timezone.localdate(target.start).isoformat())
            wait('document.querySelector("select")?.value==="" || document.querySelector("select")?.selectedIndex===0')
            wait('document.querySelector('+json.dumps(f'select option[value="{target.pk}"]')+')')
            input_value('select',str(target.pk));click('确认改期')
            wait('document.body.textContent.includes("改期成功")')
            screenshot('student-reschedule-mobile.png')
            login('browser-coach')
            navigate(f'/coach/students/{students[2].pk}/','browser-waiter')
            click('录入续课')
            input_value('.compact-form select','group')
            input_value('.compact-form input[type=number]','2')
            input_value('.compact-form input[type=date]',(timezone.localdate()+timedelta(days=5)).isoformat())
            click('确认录入')
            wait('document.body.textContent.includes("续课已录入")')
            navigate('/coach/lessons/batch/','批量记课')
            wait('document.querySelectorAll("fieldset select option").length>1')
            input_value('fieldset select',str(students[0].pk))
            click('再加一位学员')
            wait('document.querySelectorAll("fieldset select").length===2 && document.querySelectorAll("fieldset:nth-of-type(2) option").length>1')
            input_value('fieldset:nth-of-type(2) select',str(students[0].pk))
            click('确认记课 · 2 人各扣1次')
            wait('!!document.querySelector(".feedback.error")')
            assert DirectLesson.objects.count()==0, 'rejected duplicate batch must not write lessons'
            input_value('fieldset:nth-of-type(2) select',str(students[1].pk))
            screenshot('coach-batch-form-mobile.png')
            click('确认记课 · 2 人各扣1次')
            wait('document.body.textContent.includes("已为 2 位学员记课")')
            screenshot('coach-batch-mobile.png')
            navigate('/coach/reports/','月度经营报表')
            wait('document.querySelectorAll(".report-rows dd").length===8')
            values=js('[...document.querySelectorAll(".report-rows dd")].map(el=>el.textContent)')
            assert values[4]=='2 次' and values[5]=='1 人次',values
            screenshot('coach-report-mobile.png')
            screenshot('coach-report-desktop.png',1280,960)
            login('browser-waiter')
            navigate('/student/profile/','我的课包')
            wait('document.body.textContent.includes("7天内有课时到期")')
            click('7天内有课时到期')
            screenshot('student-wallet-mobile.png')
            print(json.dumps({'result':'passed','flows':['join waitlist','coach cancellation and automatic promotion','student reschedule with filter reset','coach renewal with expiry','atomic batch and balances','monthly report','student expiry reminder'],
                'screenshots':8,'overflow':False,'database':'disposable; instance data untouched'},ensure_ascii=False))
        finally:
            if cdp:
                try:cdp.call('Browser.close')
                except (OSError,EOFError):pass
                cdp.socket.close()
            for child in (browser_process,process):
                if child:
                    child.terminate()
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
            from django.db import connections
            connections.close_all()


if __name__=='__main__':
    main()
