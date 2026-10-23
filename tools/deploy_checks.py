"""镜像发布预检，只操作独立备份副本；终端输出只含结果和摘要。"""
COMPARE_CODE = r'''
import json, hashlib, sqlite3
from contextlib import closing
from pathlib import Path
def compare_legacy(backup, current):
    def quote(name):
        return '"' + name.replace('"','""') + '"'
    with closing(sqlite3.connect(Path(backup).as_uri()+'?mode=ro',uri=True)) as old:
        with closing(sqlite3.connect(Path(current).as_uri()+'?mode=ro',uri=True)) as new:
            tables=[row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'coaching_%' OR name='auth_user') ORDER BY name")]
            original={}
            for table in tables:
                columns=[row[1] for row in old.execute('PRAGMA table_info('+quote(table)+')') if not (table=='auth_user' and row[1]=='last_login')]
                sql='SELECT '+','.join(quote(column) for column in columns)+' FROM '+quote(table)+' ORDER BY id'
                before=old.execute(sql).fetchall()
                after=new.execute(sql).fetchall()
                assert before==after, 'Existing table changed: '+table
                original[table]=before
            assert new.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not new.execute('PRAGMA foreign_key_check').fetchall()
            digest=hashlib.sha256(json.dumps(original,sort_keys=True,default=str).encode()).hexdigest()
            print('legacy_data_preserved=PASS digest='+digest,flush=True)
'''
PREFLIGHT_NEW = r'''
import os, io, json, uuid
from datetime import timedelta
os.environ.setdefault('DJANGO_SETTINGS_MODULE','opencoach.settings')
import django
django.setup()
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import Client
from coaching import booking, lessons
from coaching.models import Student, Session, Booking
call_command('migrate',interactive=False,stdout=io.StringIO())
call_command('check',stdout=io.StringIO())
call_command('collectstatic',interactive=False,stdout=io.StringIO())
compare_legacy(settings.DATA_DIR/'original.sqlite3',settings.DATA_DIR/'db.sqlite3')
actor=get_user_model().objects.create(username='preflight-'+uuid.uuid4().hex,is_staff=True)
student=Student.objects.create(name='preflight-only')
booking.add_credit(student,'private',5,uuid.uuid4())
lesson=lessons.record_direct_lesson(student,actor,'private',timezone.localdate(),'preflight',uuid.uuid4())
assert booking.balances(student,'private')['remaining']==4
start=timezone.now()-timedelta(hours=2)
course=Session.objects.create(title='preflight-only',kind='private',start=start,end=start+timedelta(hours=1),location='preflight',capacity=1)
item=Booking.objects.create(student=student,session=course,operation_key=uuid.uuid4())
client=Client(HTTP_HOST='coach.qtedu.ac.cn')
index=client.get('/coach/lessons/new/')
assert index.status_code==200 and index['Cache-Control']=='no-store'
assert b'id="app"' in b''.join(index.streaming_content)
assert client.get('/api/v1/unknown/').status_code==404
assert client.get('/static/h5/missing.js').status_code==404
client.force_login(actor)
assert client.get('/api/v1/coach/dashboard/').status_code==200
state=settings.DATA_DIR/'preflight.json'
state.write_text(json.dumps({'student_id':student.id,'actor_id':actor.id,'booking_id':item.id}))
state.chmod(0o600)
print('new_image_migration_spa_api=PASS',flush=True)
'''
PREFLIGHT_OLD = r'''
import os, io, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','opencoach.settings')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client
from coaching.models import Student
from coaching.booking import balances, finish
call_command('migrate',interactive=False,stdout=io.StringIO())
call_command('collectstatic',interactive=False,stdout=io.StringIO())
state=json.loads((settings.DATA_DIR/'preflight.json').read_text())
student=Student.objects.get(pk=state['student_id'])
actor=get_user_model().objects.get(pk=state['actor_id'])
assert balances(student,'private')=={'remaining':4,'reserved':1,'available':3}
finish(state['booking_id'],actor,'completed')
assert balances(student,'private')=={'remaining':3,'reserved':0,'available':3}
client=Client(HTTP_HOST='coach.qtedu.ac.cn')
client.force_login(actor)
assert client.get('/coach/students/'+str(student.id)+'/').status_code==200
print('old_image_new_ledger_compatible=PASS',flush=True)
'''

