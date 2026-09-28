# Changelog

Все заметные изменения проекта фиксируются здесь.

## [Unreleased]

### Added
- Начальный scaffold модульного монолита Django + React/Vite.
- Docker Compose для PostgreSQL, Redis, backend и frontend.
- Базовый health endpoint и стартовая страница участника.
- Документы требований, архитектуры, защиты данных и запуска.
- UI/E2E-тесты на Playwright (`e2e/`) и список сценариев по FR-01…FR-12 (`project/TEST_SCENARIOS.md`).
- Доменные приложения по `ARCHITECTURE.md` и их первичные миграции: `organizations` (Organization,
  License, Stream), `identity` (StaffProfile с ролями FR-12, AuditEvent), `participants`
  (ParticipantToken, ConsentRecord, StageProgress), `assessments` (QuestionnaireVersion, Question,
  AnswerOption, AnswerResponse, ScoringResult), `reporting` (PersonalReportSnapshot, AggregateSnapshot,
  ExportArtifact).
- Публичный API и маршрут участника FR-01, FR-02, FR-03, FR-04, FR-06: вход по корпоративному
  `entry_code`, welcome-экран, экран согласия (журнал версии и факта, отдельно от прочих
  подтверждений), автоматическое определение этапа «вход/итог» и прохождение вопросов с прогрессом,
  идемпотентным автосохранением, возвратом назад и восстановлением сессии по токену
  (`apps/participants/services.py`, `views.py`, frontend `src/components/*`, `src/App.tsx`).
  Методики-заглушки для сквозной проверки — `manage.py seed_dummy_questionnaire`, демо-организация —
  `manage.py seed_demo_organization`.
- Backend-тесты (`pytest-django`) на модели и на весь сценарий FR-01–FR-06; UI/API e2e-тесты
  (Playwright) для тех же требований, ранее существовавшие как заготовки.
- Scoring и персональный отчёт FR-07/FR-08: `apps/assessments/scoring.py` считает баллы и зону по
  каждому из 5 отчётных показателей автоматически при завершении этапа; `apps/reporting/services.py`
  собирает отчёт «было → стало → изменение → нейтральная интерпретация», отдельный профиль EQ-5D
  (компоненты кроме VAS) и текстовый вывод по разнонаправленной/однонаправленной динамике — без
  объединения методик в общий индекс. Новый endpoint `GET /participant/reports/{token}/`
  (`project/API_SPEC.md`). Frontend: `ReportScreen` вместо статической заглушки.
  Формулы и границы зон — черновые placeholder’ы, не заменяют методологическое подтверждение.

### Not implemented yet
- Реальные версии, формулы и границы зон EQ-5D, Спилбергера–Ханина и HADS (сейчас используется
  опросник-заглушка и черновой scoring; ждём подтверждения методолога — ТЗ FR-05, FR-07.1/07.2).
- Employer dashboard, PDF/XLSX-экспорт, PRODEX Admin UI и RBAC-аутентификация сотрудников (FR-09–FR-12);
  сейчас в DRF стоит `AllowAny`.
