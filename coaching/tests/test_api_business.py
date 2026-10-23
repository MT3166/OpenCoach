import uuid
from datetime import timedelta
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from coaching import accounts, booking, training
from coaching.models import Booking, CreditEntry, Student, Submission, TrainingRecord
from .helpers import make_student, make_session

@override_settings(ALLOWED_HOSTS=['testserver','coach.qtedu.ac.cn'])
class ApiBusinessTests(TestCase):
    def setUp(self):
        self.coach = get_user_model().objects.create_user('business-coach', is_staff=True)
        self.student = make_student('business-student', credits=5)
        self.other = make_student('business-other', credits=2)
        self.course = make_session()
        self.client.force_login(self.coach)

    def post(self, path, data):
        return self.client.post('/api/v1/'+path, data, content_type='application/json')

    def test_dashboards_require_role_and_login(self):
        self.assertEqual(Client().get('/api/v1/coach/dashboard/').status_code,401)
        self.client.force_login(self.student.user)
        self.assertEqual(self.client.get('/api/v1/coach/dashboard/').status_code,403)
        self.assertEqual(self.client.get('/api/v1/student/dashboard/').status_code,200)

    def test_student_home_contains_only_their_booking(self):
        item = booking.reserve(self.student,self.course.id,uuid.uuid4())
        self.client.force_login(self.student.user)
        response = self.client.get('/api/v1/student/dashboard/')
        self.assertEqual(response.status_code,200)
        self.assertEqual([row['id'] for row in response.json()['data']['upcoming']],[item.id])
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get('/api/v1/student/dashboard/').json()['data']['upcoming'],[])

    def test_student_create_and_invite_https(self):
        response = self.post('coach/students/',{'name':'待加入学员'})
        self.assertEqual(response.status_code,201)
        student_id = response.json()['data']['id']
        response = self.client.post(f'/api/v1/coach/students/{student_id}/invitations/',{},content_type='application/json',HTTP_HOST='coach.qtedu.ac.cn',HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code,201)
        self.assertTrue(response.json()['data']['url'].startswith('https://coach.qtedu.ac.cn/invite/'))

    def test_purchase_retries_once_and_boolean_rejected(self):
        path = f'coach/students/{self.student.id}/credits/'
        payload = {'kind':'private','units':10,'operation_key':str(uuid.uuid4())}
        first = self.post(path,payload)
        self.assertEqual(first.status_code,201)
        self.assertEqual(self.post(path,payload).status_code,200)
        self.assertEqual(booking.balances(self.student,'private')['remaining'],15)
        payload.update(units=True,operation_key=str(uuid.uuid4()))
        bad = self.post(path,payload)
        self.assertEqual(bad.status_code,400)
        self.assertIn('units',bad.json()['error']['fields'])

    def test_students_cannot_modify_coach_business(self):
        self.client.force_login(self.student.user)
        paths = ['coach/students/',f'coach/students/{self.student.id}/invitations/',f'coach/students/{self.student.id}/credits/','coach/sessions/','coach/lessons/']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.post(path,{}).status_code,403)

    def test_session_creation_validates_capacity_boolean_and_conflict(self):
        start = timezone.now()+timedelta(hours=80)
        payload = {'title':'私教','kind':'private','start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat(),'location':'训练室','capacity':True}
        self.assertEqual(self.post('coach/sessions/',payload).status_code,400)
        payload['capacity'] = 1
        self.assertEqual(self.post('coach/sessions/',payload).status_code,201)
        self.assertEqual(self.post('coach/sessions/',payload).status_code,409)

    def test_reservation_retries_and_rejects_forged_student(self):
        self.client.force_login(self.student.user)
        payload = {'session_id':self.course.id,'operation_key':str(uuid.uuid4()),'student_id':self.other.id}
        self.assertEqual(self.post('student/bookings/',payload).status_code,400)
        del payload['student_id']
        first = self.post('student/bookings/',payload)
        self.assertEqual(first.status_code,201)
        second = self.post('student/bookings/',payload)
        self.assertEqual(second.status_code,200)
        self.assertEqual(first.json()['data']['id'],second.json()['data']['id'])

    def test_other_student_cannot_cancel_booking(self):
        item = booking.reserve(self.student,self.course.id,uuid.uuid4())
        self.client.force_login(self.other.user)
        self.assertEqual(self.post(f'student/bookings/{item.id}/cancel/',{}).status_code,404)
        item.refresh_from_db()
        self.assertEqual(item.status,'booked')

    def test_finish_once_and_text_only_record(self):
        item = Booking.objects.create(student=self.student,session=make_session(offset=-2),operation_key=uuid.uuid4())
        path = f'coach/bookings/{item.id}/finish/'
        self.assertEqual(self.post(path,{'outcome':'completed'}).status_code,200)
        self.assertEqual(self.post(path,{'outcome':'completed'}).status_code,200)
        self.assertEqual(CreditEntry.objects.filter(booking=item).count(),1)
        response = self.client.put(f'/api/v1/coach/bookings/{item.id}/record/',{'exercises':[],'note':'划船，注意膝盖方向'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(TrainingRecord.objects.get(booking=item).note,'划船，注意膝盖方向')

    def direct_payload(self, student=None):
        return {'student_id':(student or self.student).id,'kind':'private','occurred_on':timezone.localdate().isoformat(),'note':'','operation_key':str(uuid.uuid4())}

    def test_direct_lesson_without_booking_and_retry(self):
        payload = self.direct_payload()
        first = self.post('coach/lessons/',payload)
        self.assertEqual(first.status_code,201)
        second = self.post('coach/lessons/',payload)
        self.assertEqual(second.status_code,200)
        self.assertEqual(first.json()['data']['lesson']['id'],second.json()['data']['lesson']['id'])
        self.assertEqual(Booking.objects.count(),0)
        self.assertEqual(booking.balances(self.student,'private')['remaining'],4)
        lesson_id = first.json()['data']['lesson']['id']
        self.assertEqual(CreditEntry.objects.filter(direct_lesson_id=lesson_id).count(),1)

    def test_direct_lesson_note_edit_does_not_charge(self):
        first = self.post('coach/lessons/',self.direct_payload())
        self.assertEqual(first.status_code,201)
        lesson_id = first.json()['data']['lesson']['id']
        response = self.client.patch(f'/api/v1/coach/lessons/{lesson_id}/',{'note':'深蹲、划船'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['data']['lesson']['note'],'深蹲、划船')
        self.assertEqual(booking.balances(self.student,'private')['remaining'],4)

    def test_patch_exercises_preserves_existing_note(self):
        payload=self.direct_payload()
        payload['note']='已有课后总结'
        response=self.post('coach/lessons/',payload)
        self.assertEqual(response.status_code,201)
        lesson_id=response.json()['data']['lesson']['id']
        changed=self.client.patch(f'/api/v1/coach/lessons/{lesson_id}/',{'exercises':[{'name':'划船','reps':8}]},content_type='application/json')
        self.assertEqual(changed.status_code,200)
        self.assertEqual(changed.json()['data']['lesson']['note'],'已有课后总结')
        self.assertEqual(booking.balances(self.student,'private')['remaining'],4)

    def test_direct_lesson_does_not_take_reserved_credit(self):
        student = make_student('reserved-all',credits=1)
        booking.reserve(student,self.course.id,uuid.uuid4())
        self.assertEqual(self.post('coach/lessons/',self.direct_payload(student)).status_code,409)
        self.assertEqual(booking.balances(student,'private'),{'remaining':1,'reserved':1,'available':0})

    def test_direct_lesson_supports_unregistered_student_and_past_date(self):
        student = accounts.create_student('尚未注册')
        booking.add_credit(student,'private',2,uuid.uuid4())
        payload = self.direct_payload(student)
        payload['occurred_on'] = (timezone.localdate()-timedelta(days=2)).isoformat()
        self.assertEqual(self.post('coach/lessons/',payload).status_code,201)
        student.refresh_from_db()
        self.assertIsNone(student.user_id)

    def test_direct_future_date_and_boolean_exercise_rejected(self):
        payload = self.direct_payload()
        payload['occurred_on'] = (timezone.localdate()+timedelta(days=1)).isoformat()
        self.assertEqual(self.post('coach/lessons/',payload).status_code,400)
        payload['occurred_on'] = timezone.localdate().isoformat()
        payload['exercises'] = [{'name':'深蹲','reps':True}]
        self.assertEqual(self.post('coach/lessons/',payload).status_code,400)
        self.assertEqual(booking.balances(self.student,'private')['remaining'],5)

    def test_direct_same_day_multiple_lessons_and_key_conflict(self):
        payload = self.direct_payload()
        self.assertEqual(self.post('coach/lessons/',payload).status_code,201)
        payload['student_id'] = self.other.id
        self.assertEqual(self.post('coach/lessons/',payload).status_code,409)
        self.assertEqual(self.post('coach/lessons/',self.direct_payload()).status_code,201)
        self.assertEqual(booking.balances(self.student,'private')['remaining'],3)

    def test_direct_history_and_details_are_private(self):
        response = self.post('coach/lessons/',self.direct_payload())
        self.assertEqual(response.status_code,201)
        lesson_id = response.json()['data']['lesson']['id']
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get(f'/api/v1/student/lessons/{lesson_id}/').status_code,404)
        self.assertEqual(self.client.get('/api/v1/student/lessons/').json()['data']['items'],[])
        self.client.force_login(self.student.user)
        self.assertEqual(self.client.get('/api/v1/student/lessons/').json()['data']['items'][0]['id'],lesson_id)

    def test_history_combines_booking_and_direct_sources(self):
        item = Booking.objects.create(student=self.student,session=make_session(offset=-2),operation_key=uuid.uuid4())
        booking.finish(item.id,self.coach,'completed')
        self.assertEqual(self.post('coach/lessons/',self.direct_payload()).status_code,201)
        response = self.client.get(f'/api/v1/coach/lessons/?student_id={self.student.id}')
        self.assertEqual(response.status_code,200)
        self.assertEqual({row['source'] for row in response.json()['data']['items']},{'direct','booking'})

    def test_training_plan_submission_and_feedback(self):
        payload = {'student_id':self.student.id,'booking_id':None,'title':'课后练习','due_date':timezone.localdate().isoformat(),'exercises':[{'name':'划船','reps':12}],'note':''}
        response = self.post('coach/plans/',payload)
        self.assertEqual(response.status_code,201)
        plan_id = response.json()['data']['id']
        self.client.force_login(self.student.user)
        body = {'exercises':[{'name':'划船','reps':12,'weight':'9.5'}],'note':'完成','intent':'submit'}
        path = f'/api/v1/student/plans/{plan_id}/submission/'
        self.assertEqual(self.client.put(path,body,content_type='application/json').status_code,200)
        self.client.force_login(self.coach)
        submission = Submission.objects.get(plan_id=plan_id)
        self.assertEqual(self.client.put(f'/api/v1/coach/submissions/{submission.id}/feedback/',{'feedback':'继续保持'},content_type='application/json').status_code,200)
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get(f'/api/v1/student/plans/{plan_id}/').status_code,404)

    def test_invalid_filters_are_json_400(self):
        for suffix in ['coach/students/?page_size=101','coach/sessions/?day=bad','coach/sessions/?kind=bad','coach/bookings/?status=bad']:
            with self.subTest(suffix=suffix):
                response = self.client.get('/api/v1/'+suffix)
                self.assertEqual(response.status_code,400)
                self.assertIn('error',response.json())
