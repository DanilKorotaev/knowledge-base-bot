# Инструкции по развертыванию

## Развертывание с Docker

### 1. Подготовка

Создайте `.env` файл с необходимыми переменными окружения (см. `.env.example`).

### 2. Запуск с Docker Compose

```bash
docker-compose up -d
```

### 3. Проверка работы

```bash
docker-compose logs -f bot
```

## Развертывание на сервере

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка systemd

Создайте файл `/etc/systemd/system/knowledge-base-bot.service`:

```ini
[Unit]
Description=Telegram Knowledge Base Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/knowledge-base-bot
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/knowledge-base-bot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Запуск сервиса

```bash
sudo systemctl enable knowledge-base-bot
sudo systemctl start knowledge-base-bot
sudo systemctl status knowledge-base-bot
```

## Мониторинг

Проверяйте логи:
```bash
journalctl -u knowledge-base-bot -f
```

## Обновление

1. Остановите бота
2. Обновите код: `git pull`
3. Обновите зависимости: `pip install -r requirements.txt`
4. Запустите бота снова

