from django.urls import path
from . import views
from opencoach.frontend import page

urlpatterns = [
    path('', page(views.home), name='home'),
    path('login/', page(views.login), name='login'),
    path('logout/', page(views.logout), name='logout'),
    path('invite/<str:token>/', page(views.invite), name='invite'),
    path('coach/', page(views.coach_home), name='coach_home'),
    path('coach/lessons/', page()),
    path('coach/lessons/new/', page()),
    path('coach/lessons/batch/', page()),
    path('coach/reports/', page()),
    path('coach/lessons/<int:pk>/', page()),
    path('coach/bookings/', page()),
    path('coach/plans/', page()),
    path('coach/sessions/', page(views.coach_sessions), name='coach_sessions'),
    path('coach/sessions/<int:pk>/', page(views.coach_session), name='coach_session'),
    path('coach/students/', page(views.coach_students), name='coach_students'),
    path('coach/students/<int:pk>/', page(views.coach_student), name='coach_student'),
    path('coach/bookings/<int:pk>/', page(views.coach_booking), name='coach_booking'),
    path('coach/plans/<int:pk>/', page(views.coach_plan), name='coach_plan'),
    path('student/', page(views.student_home), name='student_home'),
    path('student/sessions/', page(views.student_sessions), name='student_sessions'),
    path('student/bookings/', page(views.student_bookings), name='student_bookings'),
    path('student/bookings/<int:pk>/cancel/', page(views.student_cancel), name='student_cancel'),
    path('student/training/', page(views.student_training), name='student_training'),
    path('student/plans/<int:pk>/', page(views.student_plan), name='student_plan'),
    path('student/profile/', page(views.student_profile), name='student_profile'),
]
