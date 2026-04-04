# Build from repository root: docker compose build health-sync-api
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY health-sync-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/health_linking/health_linking ./health_linking/
COPY health-sync-api/app ./app/

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
