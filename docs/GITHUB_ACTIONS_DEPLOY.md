# Автоматический деплой через GitHub Actions

Workflow `.github/workflows/deploy.yml` автоматически деплоит бота при push в `main`.

---

## Как это работает

```
Push в main → GitHub Actions → SSH на сервер → git pull + docker compose build + up → Telegram-уведомление
```

**Триггеры:**
- Push в `main` (кроме `docs/` и `*.md`)
- Ручной запуск через GitHub UI (Actions → Deploy Bot → Run workflow)

**Что делает workflow:**
1. Подключается к серверу по SSH
2. `git pull origin main`
3. `docker compose build bot`
4. `docker compose up -d bot`
5. Ждёт 15 секунд, проверяет health контейнера
6. Отправляет результат в Telegram

---

## Настройка (одноразовая)

### 1. SSH-ключ для GitHub Actions → сервер

На **локальной машине** (не на сервере):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/gh_actions_deploy -N ""
```

Скопировать публичный ключ на **сервер**:

```bash
ssh-copy-id -i ~/.ssh/gh_actions_deploy.pub root@YOUR_SERVER_IP
```

Или вручную добавить содержимое `~/.ssh/gh_actions_deploy.pub` в `/root/.ssh/authorized_keys` на сервере.

### 2. GitHub Secrets

В репозитории: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Значение | Пример |
|--------|----------|--------|
| `SERVER_HOST` | IP или домен сервера | `YOUR_SERVER_IP` |
| `SERVER_USER` | SSH-пользователь | `root` |
| `SSH_PRIVATE_KEY` | Содержимое `~/.ssh/gh_actions_deploy` (приватный ключ) | `-----BEGIN OPENSSH...` |
| `SERVER_PORT` | SSH-порт (если не 22) | `22` |
| `TELEGRAM_BOT_TOKEN` | Токен **основного бота БЗ** (из `.env` на сервере) | `123456:ABC...` |
| `TELEGRAM_ADMIN_CHAT_ID` | Твой личный Telegram ID (chat с ботом БЗ) | `123456789` |

> **Приватный ключ** — содержимое файла целиком, включая `-----BEGIN` и `-----END` строки.

> **Уведомления приходят в тот же чат**, где ты общаешься с ботом базы знаний. Технически GitHub Actions отправляет сообщение через Telegram Bot API (curl), используя токен основного бота. Для пользователя это выглядит как обычное сообщение от бота.

### 3. Проверка

1. Сделайте любой коммит в `main` и запушьте
2. Откройте **Actions** в репозитории на GitHub
3. Должен запуститься workflow «Deploy Bot»
4. После завершения — придёт Telegram-уведомление

---

## Ручной деплой

### Через GitHub UI

**Actions → Deploy Bot → Run workflow** → указать причину → Run

### Через серверный скрипт

```bash
ssh YOUR_SERVER "/opt/knowledge-base-bot/scripts/deploy.sh --logs 20"
```

С уведомлением в Telegram:

```bash
ssh YOUR_SERVER "/opt/knowledge-base-bot/scripts/deploy.sh --notify --logs 20"
```

### Rollback на тег

```bash
ssh YOUR_SERVER "/opt/knowledge-base-bot/scripts/deploy.sh --rollback v0.2.0 --notify"
```

---

## Git credentials для push из контейнера

Чтобы Cursor CLI (внутри Docker-контейнера) мог коммитить и пушить код от вашего имени, нужно настроить:
1. SSH-ключ для доступа к GitHub
2. Git-идентификацию (имя и email для коммитов)

### Вариант A: SSH Deploy Key (рекомендуется)

Ключ живёт только на сервере, в репозитории ничего не хранится.

**На сервере:**

```bash
# Сгенерировать ключ
ssh-keygen -t ed25519 -C "knowledge-base-bot-deploy" -f /root/.ssh/github_deploy_key -N ""

# Показать публичный ключ (для GitHub)
cat /root/.ssh/github_deploy_key.pub
```

**На GitHub:** Репозиторий → Settings → Deploy keys → Add deploy key:
- Title: `Bot Deploy Key`
- Key: содержимое `github_deploy_key.pub`
- ✅ Allow write access

**В `docker-compose.prod.yml` добавить volumes:**

```yaml
services:
  bot:
    volumes:
      # ... существующие volumes ...
      # Git: SSH-ключ для push в GitHub
      - /root/.ssh/github_deploy_key:/root/.ssh/id_ed25519:ro
      - /root/.ssh/known_hosts:/root/.ssh/known_hosts:ro
```

> Убедитесь, что `github.com` есть в known_hosts:
> ```bash
> ssh-keyscan github.com >> /root/.ssh/known_hosts
> ```

**В `.env` на сервере (не коммитить):**

```bash
# Git identity для коммитов из контейнера
GIT_AUTHOR_NAME=Your Name
GIT_AUTHOR_EMAIL=your@email.com
GIT_COMMITTER_NAME=Your Name
GIT_COMMITTER_EMAIL=your@email.com
```

**Настройка git remote в контейнере** (один раз):

```bash
docker exec -it knowledge-base-bot bash

# Внутри контейнера: если есть клон репозитория
cd /opt/knowledge-base-bot  # или где лежит репо
git remote set-url origin git@github.com:YOUR_USERNAME/knowledge-base-bot.git
```

### Вариант Б: GitHub Personal Access Token (PAT)

Если SSH неудобен, можно использовать fine-grained PAT:

1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Создать токен только для репозитория `knowledge-base-bot` с правами `Contents: Read and write`
3. Сохранить в файл на сервере: `echo "TOKEN" > /root/.github_pat && chmod 600 /root/.github_pat`
4. Смонтировать в контейнер и настроить credential helper

### Вариант В: GitHub MCP Server (экспериментально)

Cursor CLI поддерживает MCP-серверы. Теоретически можно использовать GitHub MCP Server для создания коммитов через GitHub API (без локального git push):

```json
// .cursor/mcp.json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

**Ограничения:**
- Нужен Node.js в контейнере (сейчас не установлен)
- cursor-agent в headless-режиме может не полностью поддерживать MCP
- Менее естественный workflow (API вместо git push)
- Токен всё равно нужен (в env var или файле)

**Вердикт:** MCP — интересная опция на будущее, но для MVP **SSH Deploy Key** проще и надёжнее.

---

## Монтирование репозитория для push из контейнера

Сейчас код бота COPY'd в образ (`/app`), а git-репозиторий живёт на хосте (`/opt/knowledge-base-bot`). Чтобы Cursor мог пушить изменения в коде бота:

**В `docker-compose.prod.yml`:**

```yaml
services:
  bot:
    volumes:
      # ... существующие volumes ...
      # Git-репозиторий бота (для push из контейнера)
      - /opt/knowledge-base-bot:/opt/knowledge-base-bot
```

Cursor сможет модифицировать файлы в `/opt/knowledge-base-bot` (это полный git-репозиторий с `.git/`) и выполнять `git add`, `git commit`, `git push`.

> **Примечание:** бот запускается из `/app` (COPY'd код), а Cursor модифицирует файлы в `/opt/knowledge-base-bot`. Изменения вступят в силу после деплоя (push → GitHub Actions → rebuild).

---

## Полный флоу: идея → реализация → деплой

```
1. Пользователь (Telegram): "Добавь команду /stats"
            │
            ▼
2. Cursor CLI (в контейнере):
   ├── Читает код в /opt/knowledge-base-bot
   ├── Реализует фичу
   ├── Тестирует (линтер, smoke test)
   ├── git add && git commit && git push
   │
   └── Отвечает: "✅ Фича реализована, код запушен. Деплой запустится автоматически."
            │
            ▼
3. GitHub Actions:
   ├── Триггер: push to main
   ├── SSH → сервер
   ├── git pull + docker compose build + up
   ├── Health check
   │
   └── Telegram: "✅ Деплой успешен"
            │
            ▼
4. Пользователь видит два сообщения:
   ├── "✅ Фича реализована, код запушен"
   └── "✅ Деплой успешен"
```

---

## Безопасность

- SSH-ключ для GitHub Actions → сервер: отдельный ключ, не основной
- Deploy Key для контейнер → GitHub: ограничен одним репозиторием
- GitHub Secrets зашифрованы, недоступны в форках и логах
- Workflow запускается только из `main` (защищённая ветка)
- Telegram-уведомления не содержат секретов

---

## Связанные файлы

- `.github/workflows/deploy.yml` — workflow
- `scripts/deploy.sh` — серверный скрипт деплоя (rollback, notify)
- `docs/DEPLOYMENT_SERVER.md` — общая инструкция по серверу
- `docs/GIT_FLOW.md` — процесс ветвления и релизов
