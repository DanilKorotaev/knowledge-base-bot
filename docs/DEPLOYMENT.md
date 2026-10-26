# Deployment

> **Актуально:** [OPS.md](OPS.md)  
> Текст ниже — исторический bot/systemd гайд; не использовать для KB App API.

---

## (Legacy) Развертывание с Docker — bot

См. также [telegram/SETUP.md](telegram/SETUP.md).

```bash
docker-compose up -d
docker-compose logs -f bot
```

Prod API сегодня деплоится через GitHub Actions → Mac mini host API, не этот systemd unit.
