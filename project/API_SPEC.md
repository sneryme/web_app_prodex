# API Spec

Базовый префикс: `/api/`.

## Health

`GET /api/health/` возвращает `{ "status": "ok", "service": "pez-digital-api" }`.

## Публичные endpoints участника (реализовано)

Доступны без аутентификации — участник не имеет логина, доступ управляется владением токена
(`apps/participants`). Полный контракт см. в `apps/participants/views.py` и `serializers.py`.

- `POST /participant/sessions/` — тело `{ "entry_code": "..." }`. Создаёт новый токен участника по
  корпоративному коду (ТЗ FR-01). 404 без создания токена, если код неизвестен.
- `GET /participant/sessions/{token}/` — состояние сессии: `consent_status`, `stage`
  (`baseline`/`followup`/`null`), список активных вопросов текущего этапа (пусто, пока согласие не
  дано) и `progress`. Этап и переход между ними сервер определяет сам (ТЗ FR-04) — в теле запроса
  этапа нет. 404, если токен не найден.
- `POST /participant/sessions/{token}/consents/` — тело
  `{ "consent_type": "data_processing"|"informed_notice", "text_version": "...", "accepted": true|false }`.
  Пишет запись в журнал согласий и возвращает обновлённое состояние сессии (ТЗ FR-03).
- `POST /participant/sessions/{token}/answers/` — тело `{ "question_id": 1, "option_id": 2, "raw_value": "" }`.
  Идемпотентно сохраняет ответ на текущий этап (ТЗ FR-06.6); 403 без согласия, 409 если активного этапа
  нет (оба этапа завершены), 400 для вопроса не из текущего набора.

Отдельного `POST .../complete` нет: переход между этапами и в состояние «оба этапа завершены»
происходит автоматически внутри `submit_answer`, как только все вопросы текущего этапа отвечены.

## Персональный отчёт (не реализовано)

- `GET /participant/reports/{token}` — планируется на этапе FR-08 (см. `ROADMAP.md`, этап 3).

## Планируемые защищённые endpoints (не реализовано)

- `/employer/streams` — потоки и агрегаты с фильтрами.
- `/employer/reports` — PDF/XLSX агрегатов.
- `/prodex/clients`, `/prodex/licenses`, `/prodex/operations` — операционный контур.

Требуют решения по аутентификации ролей (`apps/identity.StaffProfile`) — см. `ROADMAP.md`, этап 4.
Публичный API не должен возвращать работодателю или PRODEX индивидуальные ответы без отдельного
юридически подтверждённого основания.
