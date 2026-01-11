# Отправка в GitHub

Git репозиторий инициализирован, первый коммит создан согласно Git Flow.

## Текущий статус

✅ Git репозиторий инициализирован  
✅ Первый коммит создан в ветке `main`  
✅ Ветка `develop` создана  
✅ Remote настроен: `https://github.com/DanilKorotaev/knowledge-base-bot.git`

## Отправка в GitHub

Для отправки веток в GitHub выполните:

```bash
# Переключиться на main
git checkout main

# Отправить main в GitHub
git push -u origin main

# Переключиться на develop
git checkout develop

# Отправить develop в GitHub
git push -u origin develop
```

## Аутентификация

Если требуется аутентификация, используйте один из вариантов:

### Вариант 1: GitHub CLI (рекомендуется)

```bash
# Если установлен GitHub CLI
gh auth login
git push -u origin main
git push -u origin develop
```

### Вариант 2: Personal Access Token

1. Создайте Personal Access Token на GitHub:
   - Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Создайте токен с правами `repo`

2. Используйте токен при push:
   ```bash
   git push -u origin main
   # Введите username и token в качестве пароля
   ```

### Вариант 3: SSH ключ

1. Настройте SSH ключ для GitHub
2. Измените remote на SSH:
   ```bash
   git remote set-url origin git@github.com:DanilKorotaev/knowledge-base-bot.git
   git push -u origin main
   git push -u origin develop
   ```

## Проверка

После успешного push проверьте:
- https://github.com/DanilKorotaev/knowledge-base-bot
- Убедитесь, что обе ветки (`main` и `develop`) видны в репозитории

## Дальнейшая работа

После отправки в GitHub используйте Git Flow для работы с проектом:
- См. [docs/GIT_FLOW.md](docs/GIT_FLOW.md) для подробной информации
- Используйте скрипты из `scripts/` для автоматизации

