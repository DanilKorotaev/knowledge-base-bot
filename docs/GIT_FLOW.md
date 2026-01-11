# Git Flow - Процесс разработки и релизов

## Дата создания
2025-01-07

## Обзор

Данная документация описывает процесс разработки с использованием **Git Flow** — классической модели ветвления для управления разработкой и релизами.

Git Flow обеспечивает:
- ✅ Четкое разделение между разработкой и продакшеном
- ✅ Параллельную разработку нескольких фич
- ✅ Контролируемый процесс релизов
- ✅ Безопасные hotfix для продакшена

---

## Структура веток

### Основные ветки

#### `main` (production)
- **Назначение**: Стабильный код, готовый к продакшену
- **Защита**: Только через merge из `release/*` или `hotfix/*`
- **Теги**: Все релизы помечаются тегами `vX.Y.Z`
- **Деплой**: Автоматический деплой на продакшен при push

#### `develop` (development)
- **Назначение**: Основная ветка разработки
- **Источник**: Все фичи мержатся сюда
- **Статус**: Всегда содержит последние изменения
- **Деплой**: Опционально на staging окружение

### Вспомогательные ветки

#### `feature/*` (разработка фич)
- **Формат**: `feature/название-фичи` (например: `feature/cursor-cli-integration`)
- **Источник**: Создается от `develop`
- **Назначение**: Разработка новой функциональности
- **Завершение**: Мержится обратно в `develop` и удаляется

#### `release/*` (подготовка релиза)
- **Формат**: `release/vX.Y.Z` (например: `release/v0.1.0`)
- **Источник**: Создается от `develop`
- **Назначение**: Финальная подготовка релиза (обновление версий, CHANGELOG, тестирование)
- **Завершение**: Мержится в `main` и `develop`, создается тег

#### `hotfix/*` (срочные исправления)
- **Формат**: `hotfix/vX.Y.Z` (например: `hotfix/v0.1.1`)
- **Источник**: Создается от `main` (последнего релиза)
- **Назначение**: Срочные исправления в продакшене
- **Завершение**: Мержится в `main` и `develop`, создается тег

---

## Процессы работы

### 1. Разработка новой фичи (Feature)

#### 1.1. Создание feature-ветки

```bash
# Обновить develop
git checkout develop
git pull origin develop

# Создать feature-ветку
git checkout -b feature/cursor-cli-integration develop
```

**Или используйте скрипт:**
```bash
./scripts/git_flow_feature.sh start cursor-cli-integration
```

#### 1.2. Разработка

```bash
# Работа над фичей
git add .
git commit -m "feat: добавлена интеграция с Cursor CLI"
git push origin feature/cursor-cli-integration
```

#### 1.3. Завершение feature

```bash
# Обновить develop
git checkout develop
git pull origin develop

# Мерж feature-ветки
git merge --no-ff feature/cursor-cli-integration

# Удалить локальную ветку
git branch -d feature/cursor-cli-integration

# Удалить удаленную ветку
git push origin --delete feature/cursor-cli-integration
```

**Или используйте скрипт:**
```bash
./scripts/git_flow_feature.sh finish cursor-cli-integration
```

---

### 2. Подготовка релиза (Release)

#### 2.1. Создание release-ветки

```bash
# Обновить develop
git checkout develop
git pull origin develop

# Создать release-ветку
git checkout -b release/v0.1.0 develop
```

**Или используйте скрипт:**
```bash
./scripts/git_flow_release.sh start 0.1.0
```

#### 2.2. Подготовка релиза

В release-ветке выполните:

1. **Обновить CHANGELOG.md**:
   - Переместить записи из `[Unreleased]` в раздел `[0.1.0]`
   - Добавить дату релиза

2. **Обновить README.md**:
   - Обновить версию в файле (если нужно)

3. **Финальное тестирование**:
   - Проверить все изменения
   - Убедиться, что нет критических багов

4. **Закоммитить изменения**:
   ```bash
   git add CHANGELOG.md README.md
   git commit -m "chore: подготовка к релизу v0.1.0"
   git push origin release/v0.1.0
   ```

#### 2.3. Завершение release

```bash
# Мерж в main
git checkout main
git pull origin main
git merge --no-ff release/v0.1.0

# Создать тег
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0

# Мерж в develop (чтобы develop получил изменения из release)
git checkout develop
git pull origin develop
git merge --no-ff release/v0.1.0
git push origin develop

# Удалить release-ветку
git branch -d release/v0.1.0
git push origin --delete release/v0.1.0
```

**Или используйте скрипт:**
```bash
./scripts/git_flow_release.sh finish 0.1.0
```

**После завершения release:**
- Создайте релиз на GitHub через веб-интерфейс
- Автоматический деплой запустится при создании тега (если настроен)

---

### 3. Срочное исправление (Hotfix)

#### 3.1. Создание hotfix-ветки

```bash
# Обновить main
git checkout main
git pull origin main

# Создать hotfix-ветку от последнего релиза
git checkout -b hotfix/v0.1.1 main
```

**Или используйте скрипт:**
```bash
./scripts/git_flow_hotfix.sh start 0.1.1
```

#### 3.2. Исправление

```bash
# Внести исправления
git add .
git commit -m "fix: исправлена ошибка обработки голосовых сообщений"
git push origin hotfix/v0.1.1
```

#### 3.3. Завершение hotfix

```bash
# Обновить CHANGELOG.md
# Обновить версию в README.md (если нужно)

# Мерж в main
git checkout main
git pull origin main
git merge --no-ff hotfix/v0.1.1

# Создать тег
git tag -a v0.1.1 -m "Hotfix version 0.1.1"
git push origin v0.1.1

# Мерж в develop (чтобы develop получил исправления)
git checkout develop
git pull origin develop
git merge --no-ff hotfix/v0.1.1
git push origin develop

# Удалить hotfix-ветку
git branch -d hotfix/v0.1.1
git push origin --delete hotfix/v0.1.1
```

**Или используйте скрипт:**
```bash
./scripts/git_flow_hotfix.sh finish 0.1.1
```

---

## Визуализация Git Flow

```
main         *---*---*---*---*---*---*---*---*---* (v0.1.0) (v0.1.1)
              \         /           /       /
               \       /           /       /
                \     /           /       /
develop          *---*---*---*---*---*---*---*---*
                 \   /           /       /
                  \ /           /       /
feature/...       *---*       /       /
                           /       /
release/v0.1.0            *---*   /
                                       /
hotfix/v0.1.1                        *---*
```

---

## Правила и соглашения

### Именование веток

- **Feature**: `feature/название-фичи` (kebab-case, без пробелов)
- **Release**: `release/vX.Y.Z` (строго семантическое версионирование)
- **Hotfix**: `hotfix/vX.Y.Z` (строго семантическое версионирование)

### Коммиты

Используйте [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - новая функциональность
- `fix:` - исправление ошибки
- `docs:` - изменения в документации
- `style:` - форматирование, отсутствующие точки с запятой и т.д.
- `refactor:` - рефакторинг кода
- `test:` - добавление тестов
- `chore:` - обновление задач сборки, настроек и т.д.

**Примеры:**
```bash
git commit -m "feat: добавлена интеграция с Cursor CLI"
git commit -m "fix: исправлена ошибка обработки голосовых сообщений"
git commit -m "docs: обновлена документация по Git Flow"
```

### Защита веток

Рекомендуется настроить защиту веток в GitHub:

1. **Settings** → **Branches** → **Add rule**
2. Для `main`:
   - ✅ Require pull request reviews
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date
3. Для `develop`:
   - ✅ Require pull request reviews (опционально)
   - ✅ Require branches to be up to date

---

## CI/CD и Git Flow

### Автоматический деплой

Workflow может быть настроен для автоматического деплоя:

- **Из `main`**: Автоматический деплой на продакшен
- **Из `release/*`**: Опционально на staging (если настроено)
- **При создании тега**: Автоматический деплой релиза

### Настройка workflow

См. `.github/workflows/deploy.yml` для деталей настройки (если настроен).

---

## Скрипты автоматизации

Для упрощения работы с Git Flow созданы скрипты:

- `scripts/git_flow_feature.sh` - работа с feature-ветками
- `scripts/git_flow_release.sh` - работа с release-ветками
- `scripts/git_flow_hotfix.sh` - работа с hotfix-ветками

**Использование:**
```bash
# Feature
./scripts/git_flow_feature.sh start название-фичи
./scripts/git_flow_feature.sh finish название-фичи

# Release
./scripts/git_flow_release.sh start 0.1.0
./scripts/git_flow_release.sh finish 0.1.0

# Hotfix
./scripts/git_flow_hotfix.sh start 0.1.1
./scripts/git_flow_hotfix.sh finish 0.1.1
```

Подробнее см. документацию в самих скриптах.

---

## Часто задаваемые вопросы

### Q: Можно ли работать напрямую в develop?

**A:** Да, для небольших изменений (исправления документации, мелкие багфиксы) можно коммитить напрямую в `develop`. Для новых фич рекомендуется использовать `feature/*` ветки.

### Q: Что делать, если нужно отменить feature?

**A:** Просто удалите feature-ветку без мержа:
```bash
git branch -D feature/название-фичи
git push origin --delete feature/название-фичи
```

### Q: Можно ли мержить несколько feature в один release?

**A:** Да, все feature из `develop` попадут в release при создании release-ветки.

### Q: Что делать, если hotfix конфликтует с develop?

**A:** Разрешите конфликты при мерже hotfix в develop:
```bash
git checkout develop
git merge hotfix/v0.1.1
# Разрешить конфликты
git commit
git push origin develop
```

### Q: Нужно ли обновлять версию в hotfix?

**A:** Да, hotfix увеличивает PATCH версию (0.1.0 → 0.1.1). Обновите CHANGELOG.md и версию в README.md.

---

## Связанная документация

- [SETUP.md](SETUP.md) - Инструкции по установке и настройке
- [DEVELOPMENT.md](DEVELOPMENT.md) - Руководство для разработчиков
- [DEPLOYMENT.md](DEPLOYMENT.md) - Инструкции по развертыванию

---

**Документ создан:** 2025-01-07  
**Версия:** 1.0  
**Автор:** AI Agent

