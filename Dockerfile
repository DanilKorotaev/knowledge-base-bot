FROM python:3.11-slim

# Dual-mode agent: Linux cursor-agent in this image; macOS host installs its own binary separately.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Cursor Agent CLI (linux/arm64|amd64). Must succeed — bot cannot answer without it in Docker.
RUN curl -fsS https://cursor.com/install | bash \
    && test -x /root/.local/bin/cursor-agent \
    && /root/.local/bin/cursor-agent --version
ENV PATH="/root/.local/bin:${PATH}"

# Рабочая директория
WORKDIR /app

# Пакеты health_linking, health_aggregate
ENV PYTHONPATH="/app/packages/health_linking:/app/packages/health_aggregate"

# Копировать зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код
COPY . .

# Запуск бота
CMD ["python", "bot.py"]

