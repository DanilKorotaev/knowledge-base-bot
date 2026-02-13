FROM python:3.11-slim

WORKDIR /app

# Копировать зависимости основного проекта (нужны для БД и конфигурации)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать весь код проекта (miniapp использует database, config, utils)
COPY . .

# Порт по умолчанию
EXPOSE 8080

# Запуск через uvicorn
CMD ["python", "-m", "uvicorn", "miniapp.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

