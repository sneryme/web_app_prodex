# Docker Runbook

## Локальный запуск

```bash
copy .env.example .env
docker compose up --build
```

После обновления до ИИПБ v0.1:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_iipb_methodology
```

Команда сохраняет историю прежних комплектов. Новые организации подключаются к комплекту
через Django Admin; там же задаются контакты специалиста и терапевта. Источники, ограничения
цифровых форм и требования к производственному запуску: `METHODOLOGY_IIPB.md`.

## Проверки

Создание участника для проверки итогового ИИПБ без ожидания 7 дней:

```bash
docker compose exec backend python manage.py create_test_participant
```

Команда выводит ссылку и код нового тестового участника. Входной замер уже заполнен
синтетическим контрольным примером (ИИПБ 66); после самостоятельного подтверждения согласий
в интерфейсе сразу доступен итоговый тест. Используется отдельная организация
«Тестирование ИИПБ», данные исключены из групповой аналитики. Каждый запуск создаёт новый
код; завершённые ранее тестовые прохождения не стираются.

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
