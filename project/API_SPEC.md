# API Spec: draft

Базовый префикс: `/api/`.

## Health

`GET /api/health/` возвращает `{ "status": "ok", "service": "pez-digital-api" }`.

## Планируемые публичные endpoints

- `POST /participant/sessions` — создать сессию по корпоративной ссылке.
- `GET /participant/sessions/{token}` — получить этап и прогресс.
- `POST /participant/sessions/{token}/consents` — записать отдельные согласия.
- `POST /participant/sessions/{token}/answers` — сохранить ответ идемпотентно.
- `POST /participant/sessions/{token}/complete` — завершить этап.
- `GET /participant/reports/{token}` — получить персональный отчёт.

## Планируемые защищённые endpoints

- `/employer/streams` — потоки и агрегаты с фильтрами.
- `/employer/reports` — PDF/XLSX агрегатов.
- `/prodex/clients`, `/prodex/licenses`, `/prodex/operations` — операционный контур.

Публичный API не должен возвращать работодателю или PRODEX индивидуальные ответы без отдельного юридически подтверждённого основания.
