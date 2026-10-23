from functools import wraps
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseNotAllowed, Http404

def page(legacy=None):
    def view(request, *args, **kwargs):
        if not settings.OPENCOACH_FRONTEND_ENABLED:
            if legacy:
                return legacy(request,*args,**kwargs)
            raise Http404
        if request.method not in ['GET','HEAD']:
            return HttpResponseNotAllowed(['GET','HEAD'])
        index = Path(settings.FRONTEND_DIST) / 'index.html'
        if not index.is_file():
            return HttpResponse('前端尚未构建',status=503)
        response = FileResponse(index.open('rb'),content_type='text/html; charset=utf-8')
        response['Cache-Control'] = 'no-store'
        return response
    return wraps(legacy)(view) if legacy else view
