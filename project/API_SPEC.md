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
Тогда же (`apps/assessments/scoring.py`) автоматически пересчитывается `ScoringResult` по всем
показателям, отвеченным на этом этапе (ТЗ FR-07).

## Персональный отчёт (реализовано)

- `GET /participant/reports/{token}/` — персональный отчёт «до/после» (ТЗ FR-08): `summary`,
  `improved_count`/`total_count`, `cards` (ровно 5: `indicator_code`, `label`, `before`/`after`
  `{raw_score, zone}`, `change`, `trend`), `eq5d_profile` (доп. измерения EQ-5D кроме VAS — отдельно
  от пяти карточек). 404, если токен не найден **или** отчёт ещё не готов (не пройдены оба этапа) —
  оба случая неотличимы намеренно (ТЗ FR-08.7). Формулы scoring и границы зон — черновые placeholder’ы
  до подтверждения методологом (см. `project/PROJECT_RULES.md` №5), контракт ответа при этом не
  изменится.

## Вход сотрудника (реализовано)

Лёгкая аутентификация для контура работодателя (ТЗ FR-09.1), не полный RBAC из ТЗ FR-12:
роли на действия не разграничены, аудит ведётся только по входам и выгрузкам.

- `POST /identity/login/` — тело `{ "username": "...", "password": "..." }`. Возвращает
  `{ token, role, role_display, organization }` (`organization` = `null` для ролей, не привязанных
  к организации). 401 при неверной паре логин/пароль, 403 если у пользователя нет
  `identity.StaffProfile` (то есть он не сотрудник).
- `POST /identity/logout/` — отзывает токен текущего сотрудника, 204.

Токен передаётся в заголовке `Authorization: Token <key>` (DRF `TokenAuthentication`). Маршрут
участника остаётся без аутентификации и этот заголовок не шлёт.

## Агрегаты работодателя (реализовано)

Все endpoints требуют токена сотрудника (`IsStaffMember`); аноним получает 401. Организация
ограничивается ролью: `org_admin` видит только свою, `prodex_admin` — все
(`apps/reporting/views.py::_visible_organizations`). Обращение к чужой организации даёт **404, а не
403** — намеренно, чтобы не раскрывать существование чужого `organization_id`.

- `GET /employer/organizations/` — организации, доступные текущему сотруднику: `[{id, name}]`.
- `GET /employer/organizations/{id}/streams/` — потоки для фильтра (ТЗ FR-09.3):
  `[{id, code, name, status, participant_count}]`.
- `GET /employer/organizations/{id}/overview/?stream={id}` — весь дашборд одним вызовом
  (ТЗ FR-09.2): `organization`, `stream`, `coverage.participants`,
  `completion.{baseline_completed, followup_completed}` и `indicators` (ровно 5, каждый с
  `baseline`/`followup`/`trend`). Группы меньше `Stream.min_group_size` отдаются **без** `mean` и
  `zone_distribution` — только `participant_count` и `is_suppressed: true` (ТЗ FR-09.4). Ни токенов,
  ни отдельных ответов в ответе нет и быть не может (ТЗ FR-09.5). `stream` необязателен — без него
  агрегат по всей организации. 404, если поток не принадлежит этой организации.
- `GET /employer/organizations/{id}/export/?kind=pdf|xlsx&stream={id}` — тот же агрегат файлом
  (ТЗ FR-10): `application/pdf` либо `...spreadsheetml.sheet` с `Content-Disposition: attachment`.
  Параметр называется `kind`, **не `format`**: `format` зарезервирован DRF под собственное content
  negotiation и приводит к постороннему `Http404` вместо вызова вьюхи. 400 на неизвестный формат.
  Каждая выгрузка пишется в `reporting.ExportArtifact` (файл) и в `identity.AuditEvent` (действие).

## Операционный контур PRODEX Admin (реализовано)

Все endpoints требуют `IsProdexAdmin` (ТЗ FR-11.1): аноним получает 401, администратор организации —
403 (не 404 — в отличие от employer-контура, здесь не нужно скрывать само существование раздела).

- `GET /prodex/clients/` — таблица клиентов (ТЗ FR-11.2): `[{id, name, legal_name, license, streams_count,
  participants_count}]`. `license` — актуальная (последняя по `ends_at`) лицензия юрлица или `null`;
  `{id, starts_at, ends_at, status, status_display, is_expired}` (ТЗ FR-11.3). `is_expired` считается
  от текущей даты и может не совпадать с хранимым `status`, если его давно не обновляли руками.
  Фильтры: `?search=` (по названию), `?license_status=active|expired|suspended`.
- `GET /prodex/licenses/` — все лицензии, включая историю перевыпуска (не только актуальная на
  клиента): `[{..., organization: {id, name}}]`. Фильтр `?status=`.
- `GET /prodex/operations/` — технические/операционные метрики по всей системе (ТЗ FR-11.4):
  `organizations_count`, `licenses`/`streams`/`participants` (счётчики по статусам), `completion`,
  `activity.new_participants_last_30d`, `errors.unscored_answer_groups` (пары участник/этап/
  показатель с ответами, но без `ScoringResult` — в норме 0, ненулевое значение почти всегда значит
  пропуск из-за смешанной версии методики, см. `apps/assessments/scoring.py`). Ни одного
  психологического показателя (индикатора, зоны, балла) в ответе нет и не может быть (ТЗ FR-11.5).

Публичный API не должен возвращать работодателю или PRODEX индивидуальные ответы без отдельного
юридически подтверждённого основания.
