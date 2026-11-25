# API Spec

Базовый префикс: `/api/`.

### Тестовые участники

`ParticipantToken.is_test` по умолчанию false. Устанавливается служебной командой
`create_test_participant`, не принимается публичным API. В меню, состоянии комплекта и
персональном отчёте возвращается `is_test`; интерфейс помечает тестовые данные.
Для тестового участника полный входной замер открывает итоговый сразу; согласия, порядок
вопросов и закрытие завершённых этапов действуют как обычно. Даты замеров не подменяются.
Тестовые участники исключены из счётчиков потоков, групповых показателей, сравнений и экспортов.
Операционные метрики PRODEX учитывают такие сессии как техническую активность.

## Методология ИИПБ v0.1 (24.11.2026)

Контракты прежних комплектов сохраняются. Для комплекта `methodology=iipb-0.1`:

- Список комплектов участника содержит `methodology`; не начатый снятый с публикации комплект
  скрыт, исторический остаётся доступен начавшему его участнику.
- Состояние выбранного комплекта дополнено `methodology`, `baseline_result`, `routing_contacts`,
  `followup_locked` и `followup_available_at` (ISO datetime). `baseline_result` содержит полный
  результат только после согласий новой версии. Для заблокированного итогового этапа `questions=[]`.
- `POST /participant/sessions/{token}/consents/`: для ИИПБ нужны отдельные `informed_notice`
  и `data_processing` с `text_version=iipb-0.1`; старые согласия не заменяют новые.
- `POST /participant/sessions/{token}/answers/`: для новых форм обязательны `bundle_id` и `stage`.
  409 при попытке пропустить вопрос/опросник, изменить завершённый опросник или пройти итоговый
  этап раньше 7 суток. 403 без согласий; 400 для недопустимого ответа. Сохраняется первая полная
  попытка этапа, последующие изменения закрыты.
- `GET /participant/reports/{token}/?bundle_id={id}` доступен после входного замера:
  `status=baseline_only|completed`, `iipb={baseline,followup,dynamics}`. До итогового замера
  `followup` и `dynamics` равны null. Замер содержит `version`, `version_date`, `measured_at`,
  `inputs` (10 значений), `subindices`, `domains`, `lss`, `index`, `level`, `level_label`,
  `conclusion`, `action`, `red_flags`, `yellow_flags`, `trait_marker`, `questionnaire_versions`.
  Флаги: `{code,label,action}`. Динамика: `delta_pp`, `delta_percent` (null при исходном 0),
  `level_change`, `trend`, `summary`, `notice`, `actions`. ЛТ не входит в карточки динамики.
  404 до полного входного замера; 403 без актуальных согласий.
- Employer overview/compare дополнены `iipb={version,version_date,threshold,notice,dynamics_notice,
  baseline,followup,trend}`. Этап: `participant_count`, `is_suppressed`; при n≥порога —
  `mean`, `median`, `zone_distribution`, `red_flag_count`, `yellow_flag_count`,
  `flag_distribution`, `trait_distribution`. Парная динамика: `paired_count`, `is_suppressed`;
  при достаточном числе пар — `mean_delta`, `median_delta`, `improved`, `worsened`, `stable`.
  Порог не менее 5 независимо от настройки потока. Индивидуальных входов и токенов здесь нет.
  В `indicators` новой версии 4 показателя: ЛТ только в фоновом распределении.
- PDF/XLSX/CSV содержат те же агрегаты и правила скрытия, версию ИИПБ, медианы, флаги и парную Δ.

Полная расчётная спецификация и ограничения бланков: `METHODOLOGY_IIPB.md`.

## Health

`GET /api/health/` возвращает `{ "status": "ok", "service": "pez-digital-api" }`.

## Публичные endpoints участника (реализовано)

Доступны без аутентификации — участник не имеет логина, доступ управляется владением токена
(`apps/participants`). Полный контракт см. в `apps/participants/views.py` и `serializers.py`.

- `POST /participant/sessions/` — тело `{ "entry_code": "..." }`. Создаёт новый токен участника по
  корпоративному коду (ТЗ FR-01). 404 без создания токена, если код неизвестен.
- `POST /participant/entry/` — тело `{ "entry_code": "..." }`. Возвращает `organization_id` и
  активные потоки для корпоративной ссылки. Фронтенд использует ID, чтобы продолжить сохранённую
  сессию только тогда, когда она относится к той же организации, что и открытая ссылка.
- `POST /participant/streams/` — прежний контракт списка потоков `[{id, code, name}]` сохраняется
  для совместимости.
- `GET /participant/sessions/{token}/` — состояние сессии: `organization_id`, `consent_status`, `stage`
  (`baseline`/`followup`/`null`), список активных вопросов текущего этапа (пусто, пока согласие не
  дано), `questionnaires` (методики активного комплекта с числом вопросов и ответов), а также
  `progress`. Каждый вопрос содержит `questionnaire_code`, чтобы интерфейс мог сгруппировать маршрут
  по методикам и показать меню выбора. Этап и переход между ними сервер определяет сам (ТЗ FR-04).
  Клиент передаёт полученный этап при сохранении ответа. 404, если токен не найден.
- `POST /participant/sessions/{token}/consents/` — тело
  `{ "consent_type": "data_processing"|"informed_notice", "text_version": "...", "accepted": true|false }`.
  Пишет запись в журнал согласий и возвращает обновлённое состояние сессии (ТЗ FR-03).
- `POST /participant/sessions/{token}/answers/` — например,
  `{ "bundle_id": 1, "stage": "baseline", "question_id": 1, "option_id": 2 }`.
  Поле `stage` обязательно и принимает `baseline` или `followup`. Сервер сверяет его с текущим этапом
  перед записью. Повтор со старым этапом возвращает 409 с `code=stage_mismatch`. Когда оба этапа
  завершены, сервер также возвращает 409. Без согласия возвращается 403, для запроса без этапа,
  с недопустимым этапом или вопросом из другого набора — 400.

Отдельного `POST .../complete` нет: переход между этапами и в состояние «оба этапа завершены»
происходит автоматически внутри `submit_answer`, как только все вопросы текущего этапа отвечены.
Тогда же (`apps/assessments/scoring.py`) автоматически пересчитывается `ScoringResult` по всем
показателям, отвеченным на этом этапе (ТЗ FR-07).

## Персональный отчёт (реализовано)

- `GET /participant/reports/{token}/` — персональный отчёт «до/после» (ТЗ FR-08): `summary`,
  `improved_count`/`total_count`, `cards` (до 5 для исторических комплектов: `indicator_code`, `label`, `before`/`after`
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
  `completion.{baseline_completed, followup_completed}` и `indicators` (5 исторических или 4 в ИИПБ, каждый с
  `baseline`/`followup`/`trend`). Группы меньше `Stream.min_group_size` отдаются **без** `mean` и
  `zone_distribution` — только `participant_count` и `is_suppressed: true` (ТЗ FR-09.4). Ни токенов,
  ни отдельных ответов в ответе нет и быть не может (ТЗ FR-09.5). `stream` необязателен — без него
  агрегат по всей организации. 404, если поток не принадлежит этой организации.
- `GET /employer/organizations/{id}/compare/` — сравнение групп по одному комплекту тестов.
  Для потоков: `?mode=streams&streams={id1},{id2}[,{id3},{id4}]`; допускается от 2 до 4 потоков
  организации. Для периодов: `?mode=periods&period_a_from=YYYY-MM-DD&period_a_to=YYYY-MM-DD&`
  `period_b_from=YYYY-MM-DD&period_b_to=YYYY-MM-DD`; периоды не должны пересекаться. Когорта
  определяется по дате создания сессии участника (`ParticipantToken.created_at`). Ответ содержит
  агрегат каждой группы. Для потока используется `Stream.min_group_size`, для периода — порог
  организации по умолчанию (5); порог применяется отдельно для каждого показателя, этапа и пары
  «вход/итог». При недостаточном числе результатов `mean` и `zone_distribution` не возвращаются.
  Ни токены, ни индивидуальные ответы в ответе не передаются. 404 при потоке чужой организации,
  400 при некорректном наборе групп или пересекающихся периодах.
- `GET /employer/organizations/{id}/export/?kind=pdf|xlsx|csv` — тот же агрегат файлом
  (ТЗ FR-10): PDF, XLSX или CSV с `Content-Disposition: attachment`. Поддерживает необязательные фильтры `stream={id}` и `bundle={id}`.
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
