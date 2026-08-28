# Feature: Structured UI schema v1.1 — P2 blocks

**Status:** pending  
**Vault:** `Документация/Задачи/task-structured-ui-next.md`

## Candidates (после P1: image, link, file, divider)

| Приоритет | Тип | Зачем | Сложность |
|-----------|-----|--------|-----------|
| P2 | `callout` | info / warn / tip блок в панели | низкая |
| P2 | `spacer` | вертикальный отступ без divider | низкая |
| P2 | `progress` | шаг wizard (0–1 или steps) | средняя |
| P2 | `date` / `time` | выбор без клавиатуры (напоминания, дедлайны) | средняя |
| P2 | `hstack` | горизонтальная раскладка кнопок | средняя |
| P3 | `slider` / `stepper` | числа, рейтинг | средняя |
| P3 | `confirm` | destructive button + alert | низкая (клиент) |
| P3 | `markdown` (subset) | жирный/список в `text` | высокая |
| later | `table` / `metric` | KPI — ближе к Boards | высокая |

## Done when

- [ ] Выбрать 2–3 блока для v1.1 (рекомендация: `callout` + `date` + `progress`)
- [ ] JSON Schema + validator + iOS renderer + agent prompt
- [ ] OpenAPI + contract doc

## Notes

Не смешивать с Dashboard Platform — schema может быть общей, продукт разный.
