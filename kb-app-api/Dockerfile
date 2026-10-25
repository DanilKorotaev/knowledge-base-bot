# Сборка из корня репозитория: docker compose build kb-app-api
# Нужны те же зависимости, что у бота (Cursor CLI, БД, сервисы).
#
# Dual-mode agent:
# - container/Linux (strict): this image installs linux/arm64|amd64 cursor-agent
# - host/macOS: install separately (`curl https://cursor.com/install | bash`) — never mount the macOS binary in
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Linux Cursor Agent CLI (same installer as VPS Docker). Fail the build if missing —
# silent `|| echo skipped` previously shipped images without cursor-agent.
RUN curl -fsS https://cursor.com/install | bash \
    && test -x /root/.local/bin/cursor-agent \
    && /root/.local/bin/cursor-agent --version
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
