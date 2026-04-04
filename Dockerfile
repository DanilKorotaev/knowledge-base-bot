FROM python:3.11-slim

# Установить зависимости системы
RUN apt-get update && apt-get install -y \
    curl \
    git \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Установить Cursor CLI
# Cursor CLI устанавливается через curl скрипт
RUN curl https://cursor.com/install -fsS | bash || echo "Warning: Cursor CLI installation failed, but continuing..."
ENV PATH="/root/.local/bin:${PATH}"

# Рабочая директория
WORKDIR /app

# Пакет health_linking (import health_linking)
ENV PYTHONPATH="/app/packages/health_linking"

# Копировать зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код
COPY . .

# Запуск бота
CMD ["python", "bot.py"]

