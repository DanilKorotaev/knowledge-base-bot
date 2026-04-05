# Сборка из корня репозитория: docker compose build kb-app-api
# Нужны те же зависимости, что у бота (Cursor CLI, БД, сервисы).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Cursor CLI — как в основном Dockerfile бота (без него process_query_for_api не сможет вызывать агента).
RUN curl https://cursor.com/install -fsS | bash || echo "cursor install skipped"
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8091/health')"

CMD ["uvicorn", "kb_app_api.main:app", "--host", "0.0.0.0", "--port", "8091"]
