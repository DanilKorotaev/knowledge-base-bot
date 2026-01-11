FROM python:3.11-slim

# Установить зависимости системы
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Установить Cursor CLI (опционально, если нужен)
# RUN curl https://cursor.com/install -fsS | bash
# ENV PATH="/root/.local/bin:${PATH}"

# Рабочая директория
WORKDIR /app

# Копировать зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код
COPY . .

# Запуск бота
CMD ["python", "bot.py"]

