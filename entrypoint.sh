#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn opencoach.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 45 --error-logfile - --log-level info
