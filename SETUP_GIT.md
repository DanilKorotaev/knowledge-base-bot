# Инструкция по настройке Git репозитория

## Инициализация Git репозитория (согласно Git Flow)

1. Перейдите в директорию проекта:
```bash
cd knowledge-base-bot
```

2. Инициализируйте Git репозиторий:
```bash
git init
```

3. Добавьте remote для GitHub:
```bash
git remote add origin https://github.com/DanilKorotaev/knowledge-base-bot.git
```

4. Добавьте все файлы:
```bash
git add .
```

5. Создайте первый коммит в main:
```bash
git commit -m "chore: initial commit - базовая структура проекта"
git branch -M main
```

6. Создайте ветку develop:
```bash
git checkout -b develop
```

7. Отправьте обе ветки в GitHub:
```bash
git push -u origin main
git push -u origin develop
```

## Работа с Git Flow

После инициализации используйте Git Flow для работы с проектом. См. [docs/GIT_FLOW.md](docs/GIT_FLOW.md) для подробной информации.

**Основные команды:**
- Создать feature: `./scripts/git_flow_feature.sh start название-фичи`
- Завершить feature: `./scripts/git_flow_feature.sh finish название-фичи`
- Создать release: `./scripts/git_flow_release.sh start 0.1.0`
- Создать hotfix: `./scripts/git_flow_hotfix.sh start 0.1.1`

## Проверка

После выполнения команд проверьте, что репозиторий создан:
- Откройте https://github.com/DanilKorotaev/knowledge-base-bot
- Убедитесь, что все файлы загружены

## Дальнейшая работа

Для работы с репозиторием используйте стандартные команды Git:
```bash
git status          # Проверить статус
git add .           # Добавить изменения
git commit -m "..." # Создать коммит
git push            # Отправить в GitHub
git pull            # Получить изменения
```

