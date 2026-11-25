# Playwright для ИИПБ и исторических комплектов

GitLab CI запускает оба набора в отдельных заданиях, каждое со своей PostgreSQL.
Для локального запуска установите зависимости в каталоге `e2e`.

```powershell
npm ci
npx playwright install chromium
```

## ИИПБ

Подготовьте демонстрационный стенд по [основному README](../README.md).
В PowerShell, из которого запускается Playwright, установите пароль кабинета
работодателя и код тестового участника, выведенные командой `seed_iipb_demo --test-participant`.

```powershell
$env:E2E_SUITE = 'iipb'
$env:IIPB_DEMO_STAFF_PASSWORD = '<пароль демо>'
$env:E2E_TEST_PARTICIPANT_TOKEN = '<код участника>'
npm test
```

## Исторические комплекты

На отдельном тестовом стенде с чистой базой выполните следующие команды в папке
с `docker-compose.yml`.

```powershell
docker compose exec backend python manage.py seed_demo_organization
docker compose exec backend python manage.py seed_real_questionnaires
docker compose exec backend python manage.py seed_dummy_questionnaire
docker compose exec backend python manage.py seed_employer_demo_streams --bundle prodex-v1
docker compose exec backend python manage.py seed_demo_staff
docker compose exec backend python manage.py seed_demo_licenses
```

Из каталога `e2e` запустите исторический набор.

```powershell
$env:E2E_SUITE = 'legacy'
npm test
```

`npm run test:bundle-flow` в этом режиме запускает только сценарий FR-13.
Если порты тестового стенда отличаются, задайте `E2E_BASE_URL` и `E2E_API_URL`.
