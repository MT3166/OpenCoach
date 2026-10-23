FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OPENCOACH_DATA_DIR=/app/data DJANGO_DEBUG=0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -c "from pathlib import Path; assert Path('/app/frontend/dist/index.html').is_file(), 'Build frontend before image creation'"
RUN mkdir -p /app/data /app/staticfiles && chown -R 1000:1000 /app && chmod +x /app/entrypoint.sh
USER 1000:1000
EXPOSE 8000
CMD ["/app/entrypoint.sh"]
