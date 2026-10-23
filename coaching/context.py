from django.conf import settings

def brand(request):
    return {'brand_name': settings.BRAND_NAME, 'coach_name': settings.COACH_NAME}
