# Комната ПЭЗ. Digital

Запускаемый scaffold для цифрового контура продукта PRODEX: анонимизированный маршрут тестирования «до / после», персональный отчёт участнику и агрегированная аналитика работодателю.

## Быстрый старт

```bash
copy .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health/
- Django admin: http://localhost:8000/admin/

Чтобы пройти маршрут участника локально (вход → согласие → вопросы), нужен корпоративный код и
опросник — оба даёт сид-заглушка (реальные версии EQ-5D/Спилбергера–Ханина/HADS ещё не подтверждены
методологом, см. `project/DATA_PROTECTION.md`):

```bash
docker compose exec backend python manage.py seed_demo_organization
docker compose exec backend python manage.py seed_dummy_questionnaire
```

Первая команда выводит `entry_code` — откройте `http://localhost:5173/?code=<entry_code>`.

Реализован маршрут участника FR-01…FR-04, FR-06…FR-08 (вход по коду, согласие, автоопределение
этапа, прохождение вопросов с автосохранением, автоматический scoring и персональный отчёт
«до / после»). Employer dashboard, PDF/XLSX-экспорт (FR-09, FR-10), PRODEX Admin (FR-11) и
production-аутентификация (FR-12) ещё не реализованы — см. `project/ROADMAP.md` и
`project/TEST_SCENARIOS.md`.

## UI/E2E-тесты

Playwright, папка `e2e/`. Проект должен быть запущен (`docker compose up`), плюс обе сид-команды выше.

```bash
cd e2e
npm install
npx playwright install chromium
npm test
```

Сценарии по FR-01…FR-12 описаны в `project/TEST_SCENARIOS.md`.

## Работа с GitLab

В проекте используется одна основная ветка `main`. Прямые изменения в `main` не выполняются.

### Правила ветвления

- Каждая доработка выполняется в отдельной ветке, созданной от актуальной `main`.
- Для новой функциональности используется формат `feature/<краткое-описание>`.
- Для исправления ошибки используется формат `fix/<краткое-описание>`.
- Для технических изменений используется формат `chore/<краткое-описание>`.
- Перед началом работы необходимо обновить локальную `main`:

```bash
git switch main
git pull origin main
```

- Новая ветка создаётся от обновлённой `main`:

```bash
git switch -c feature/<краткое-описание>
```

### Merge Request

- Завершённая доработка отправляется в GitLab и вливается в `main` только через Merge Request.
- В Merge Request нужно указать цель изменения, основные изменения, способ проверки и известные ограничения.
- Перед созданием Merge Request необходимо синхронизировать ветку с `main`, разрешить конфликты и проверить проект локально.
- Merge Request должен проходить code review и обязательные CI-проверки.
- В `main` вливаются только проверенные изменения, готовые к дальнейшей разработке или релизу.
- После успешного слияния рабочая ветка удаляется в GitLab и локально.

### Рекомендуемый цикл работы

```bash
git switch main
git pull origin main
git switch -c feature/<краткое-описание>

# работа над изменениями
git add .
git commit -m "feat: краткое описание изменения"
git push -u origin feature/<краткое-описание>
```

После отправки ветки создаётся Merge Request `feature/<краткое-описание>` → `main`.

Перед слиянием рекомендуется выполнить:

```bash
docker compose config
docker compose build
docker compose up -d
curl.exe -fsS http://localhost:8000/api/health/
docker compose down
```

После слияния локальная ветка удаляется:

```bash
git switch main
git pull origin main
git branch -d feature/<краткое-описание>
```

## Структура

- `backend/` — Django + DRF API.
- `frontend/` — React + TypeScript + Vite.
- `project/` — требования, правила, архитектура, privacy и roadmap.
- `docker-compose.yml` — локальная инфраструктура PostgreSQL, Redis, backend и frontend.

## Важные ограничения

- Не добавлять ФИО, телефон, e-mail или табельный номер в тестовый контур MVP.
- Работодатель получает только агрегаты; индивидуальные результаты ему не выдаются.
- Порог публикации малых групп и юридический режим обработки должны быть подтверждены до production.
- Версии и лицензии EQ-5D, Спилбергера–Ханина и HADS подтверждаются до релиза scoring.
