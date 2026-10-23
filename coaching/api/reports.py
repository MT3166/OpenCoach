import re
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from coaching.reports import monthly, month_bounds
from .common import CoachView, success


class MonthlyReportView(CoachView):
    def get(self, request):
        month = request.query_params.get('month', timezone.localdate().strftime('%Y-%m'))
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}', month):
                raise ValueError
            month_bounds(month)
        except (ValueError, OverflowError):
            raise ValidationError({'month':['请使用有效 YYYY-MM 月份（0001-02 至 9999-11）']})
        return success(monthly(month))
