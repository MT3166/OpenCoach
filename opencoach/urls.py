from django.urls import path, include, re_path
from coaching.views import health
from coaching.api.common import api_not_found

urlpatterns = [path('health/', health),
               path('api/v1/', include('coaching.api.urls')),
               re_path(r'^api(?:/.*)?$', api_not_found),
               path('', include('coaching.urls'))]
