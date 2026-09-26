# Docker Runbook

## Локальный запуск

```bash
copy .env.example .env
docker compose up --build
```

## Проверки

```bash
docker compose config
docker compose ps
curl http://localhost:8000/api/health/
```

## Остановка

```bash
docker compose down
```

Для удаления локальных данных PostgreSQL используется отдельная осознанная команда `docker compose down -v`; не запускать её автоматически.
