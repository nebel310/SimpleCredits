# USERFLOW.md

## 1. Что это за продукт

Веб-платформа умного кредитного кабинета для малого и микробизнеса. Предприниматель заходит на сайт, выбирает сумму и (опционально) кредитный продукт, заполняет данные о себе и компании, отправляет заявку. Бэкенд обогащает данные через моковые государственные сервисы, отправляет их в ML-сервис скоринга, получает решение и присваивает заявке финальный статус. Пользователь видит результат в реальном времени через WebSocket.

Финальная точка пути — статус заявки (`confirmed` / `different` / `declined` / `failed`). Дальнейшие этапы (подписание, выдача денег, сопровождение кредита) в MVP **не реализуются**.

## 2. Роли

| Роль | Что делает |
|---|---|
| `user` | Регистрируется, заполняет профиль компании, создаёт и просматривает свои заявки |
| `admin` | Просматривает все заявки, имеет доступ к статистике, управляет каталогом продуктов |

Других ролей нет. Пользователь и компания — одна сущность: у каждого `user` в профиле есть реквизиты его компании и финансовые показатели.

## 3. Основные сущности

### UserOrm

Пользователь + компания + актуальные финансовые данные.

**Базовые поля:**
- `id`, `username`, `email`, `hashed_password`, `role` (`user` / `admin`)
- `avatar_id`, `bio`, `birth_date`, `gender`
- `created_at`

**Поля компании:**
- `inn`, `ogrn`, `legal_name`, `legal_form`, `okved`, `region`, `registration_date`, `employee_count`

**Поля финансов (последние известные):**
- `annual_revenue_rub`, `annual_net_profit_rub`, `ebitda_rub`, `total_debt_rub`, `monthly_revenue_rub`, `monthly_expenses_rub`, `accounts_receivable_rub`, `cash_balance_rub`, `period_end`

**Поля кредитной истории (последние известные):**
- `active_obligations_count`, `total_outstanding_rub`, `monthly_debt_payments_rub`, `max_days_past_due_12m`, `has_current_past_due`, `credit_utilization`, `closed_obligations_count`, `applications_last_6m`

Профиль заполняется при регистрации или при первом создании заявки. Обновляется через `PATCH /auth/me`.

### ProductOrm

Каталог кредитных продуктов. См. раздел 4.

### ApplicationOrm

Кредитная заявка. Один пользователь — много заявок. Заявка хранит снимок всех данных компании и финансов на момент подачи, чтобы результат был воспроизводим.

**Поля:**
- `id`, `application_id` (uuid, публичный), `user_id`
- `status` — один из 5 (см. раздел 5)
- `product_type` — `microloan` / `term_loan` / `overdraft` / `credit_line` / `leasing` / `null`
- `requested_amount_rub`, `term_months`, `purpose`, `segment`
- Snapshot полей компании (inn, ogrn, legal_name, legal_form, okved, region, registration_date, employee_count)
- Snapshot полей финансов (8 полей)
- Snapshot полей кредитной истории (8 полей)
- `enriched_data` (JSONB) — что вернули мок-госуслуги
- `scoring_result` (JSONB) — полный ответ ML-сервиса (score, pd, risk_grade, reason_codes, decision, conditions, model_version)
- `explanation` (TEXT) — словесный комментарий от ML (LLM)
- `created_at`, `updated_at`, `submitted_at`

### ApplicationEventOrm

История событий по заявке. Пишется автоматически, читается для отображения таймлайна и для восстановления состояния после переподключения к WebSocket.

**Поля:**
- `id`, `application_id`, `event_type`, `payload` (JSONB), `created_at`

Типы событий: `created`, `enriched`, `scored`, `status_changed`, `failed`.

## 4. Продукты

### Поля ProductOrm

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | PK |
| `code` | str | Уникальный slug, например `working_capital` |
| `name` | str | Название для пользователя |
| `description` | str | Короткое описание в 1–2 предложения |
| `product_type` | str | `microloan` / `term_loan` / `overdraft` / `credit_line` / `leasing` — соответствует enum из ML |
| `segment` | str | `micro` / `small` / `both` |
| `min_amount_rub` | int | Минимальная сумма |
| `max_amount_rub` | int | Максимальная сумма |
| `min_term_months` | int | Минимальный срок |
| `max_term_months` | int | Максимальный срок |
| `rate_min_percent` | float | Минимальная ставка |
| `rate_max_percent` | float | Максимальная ставка |
| `purposes` | JSONB | Массив `purpose` (enum'ы из ML): `["working_capital", "equipment"]` |
| `features` | JSONB | Массив фич: `["Без залога", "Решение за 1 день"]` |
| `requirements` | JSONB | Массив требований: `["ИП или ООО от 6 месяцев"]` |
| `extras` | JSONB | Специфичные для типа поля (см. ниже) |
| `is_active` | bool | Показывать ли в каталоге |
| `display_order` | int | Порядок сортировки |
| `created_at`, `updated_at` | datetime | |

**Специфичные поля в `extras` по типу:**

- Овердрафт: `{ "limit_period_days": 180, "repayment_method": "auto" }`
- Кредитная линия: `{ "tranche_min_rub": 100000 }`
- Лизинг: `{ "advance_percent_min": 10, "advance_percent_max": 30, "equipment_types": ["станки", "транспорт"] }`
- Оборотный: `{ "revolving": true }`
- Микрозайм: `{ "express_decision": true }`

### Seed (начальный набор)

| code | name | product_type | segment | сумма | срок | ставка |
|---|---|---|---|---|---|---|
| `microloan` | Микрозайм | microloan | micro | 50 000 – 3 000 000 | 1–24 мес | 18–28% |
| `working_capital` | Оборотный кредит | term_loan | small | 100 000 – 30 000 000 | 3–36 мес | 15–24% |
| `overdraft` | Овердрафт | overdraft | small | 500 000 – 15 000 000 | 6–12 мес | 14–22% |
| `credit_line` | Кредитная линия | credit_line | small | 1 000 000 – 50 000 000 | 12–36 мес | 13–20% |
| `leasing` | Лизинг оборудования | leasing | small | 500 000 – 40 000 000 | 12–60 мес | 12–20% |

Seed выполняется идемпотентно при старте приложения (метод `ensure_products` в `repositories/products.py`).

### REST API продуктов

- `GET /products` — список активных продуктов, отсортированный по `display_order`
- `GET /products/{code}` — детали продукта по slug

CRUD для админа (`POST/PATCH/DELETE /admin/products`) в MVP не обязателен.

## 5. Статусы заявки

| Статус | Когда присваивается |
|---|---|
| `pending` | Заявка создана и отправлена, ждём ответа ML |
| `failed` | Произошла ошибка: ML недоступен, таймаут, сбой обогащения |
| `confirmed` | ML вернул `approve` **и** пользователь выбирал продукт, и продукт подошёл |
| `different` | ML вернул `approve_with_conditions` / `manual_review` **или** пользователь не выбирал продукт (система подобрала сама) |
| `declined` | ML вернул `decline` |

**Правила маппинга `decision` → `status`:**

```
approve + product_type указан       → confirmed
approve + product_type = null       → different
approve_with_conditions             → different
manual_review                       → different
decline                             → declined
ошибка ML / сети / обогащения       → failed
```

Промежуточный `pending` живёт от создания заявки до получения ответа ML (обычно 1–3 секунды в демо, до 30 секунд с мок-задержками).

## 6. Полный путь пользователя

### Шаг 1. Регистрация

`POST /auth/register` с `username`, `email`, `password`, `password_confirm`. Возвращается `user_id`. Роль всегда `user`.

### Шаг 2. Вход

`POST /auth/login` с `email`, `password`. Возвращается `access_token`, `refresh_token`. Дальше все запросы с `Authorization: Bearer <access_token>`.

### Шаг 3. Заполнение профиля компании (один раз)

`PATCH /auth/me` с полями компании, финансов и кредитной истории. Пользователь заполняет это один раз, дальше данные переиспользуются во всех заявках.

Альтернатива: если профиль не заполнен, при создании первой заявки фронт отправляет эти данные вместе с заявкой, бэкенд сохраняет их в профиль.

### Шаг 4. Просмотр каталога продуктов (опционально)

`GET /products` — фронт показывает карточки. Пользователь либо выбирает конкретный продукт, либо не выбирает (тогда система сама подберёт по параметрам заявки).

### Шаг 5. Создание заявки

`POST /applications` с полями:

```json
{
  "requested_amount_rub": 1500000,
  "term_months": 24,
  "purpose": "equipment",
  "segment": "small",
  "product_type": "term_loan"
}
```

`product_type` опционален. Если его нет — бэкенд всё равно отправит в ML один из типов (либо `term_loan` по умолчанию, либо выведет из `purpose`).

### Шаг 6. Обработка на бэкенде

1. Создать `ApplicationOrm` со статусом `pending`, скопировать snapshot всех данных из профиля
2. Записать событие `created`
3. **Обогащение**: последовательно вызвать мок-сервисы ЕГРЮЛ, ФНС, БКИ по ИНН пользователя. Сохранить ответы в `enriched_data`
4. Записать событие `enriched`
5. **Скоринг**: собрать `ScoreApplicationRequest` для ML из профиля + `enriched_data` + параметров заявки, вызвать gRPC `ScoreApplication`
6. Получить ответ, замапить `decision` в статус по правилам раздела 5, сохранить `scoring_result` и `explanation`
7. Записать событие `scored` и событие `status_changed`
8. **Отправить WebSocket-уведомление** пользователю, у которого открыт канал
9. Вернуть `201` с полной информацией о заявке и её статусе

При ошибке любого этапа статус меняется на `failed`, событие `failed` пишется, WebSocket-уведомление отправляется, `500 / 502 / 504` возвращается клиенту.

### Шаг 7. Отображение результата

Frontend получает WebSocket-событие `status_changed`, обновляет UI. Показывает пользователю статус, причину (из `reason_codes`), объяснение (из `explanation`), при статусе `different` — что предлагается альтернатива (из `decision.conditions` и `recommended_amount_rub`).

### Шаг 8. Просмотр заявки позже

`GET /applications/{id}` — детали. `GET /applications` — список заявок пользователя с курсорной пагинацией. `GET /applications/{id}/events` — история событий для восстановления таймлайна.

**Путь завершён.**

## 7. REST API

### Auth

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/auth/register` | Регистрация |
| POST | `/auth/login` | Вход |
| POST | `/auth/refresh` | Обновить access-токен (refresh в query) |
| POST | `/auth/logout` | Выход |
| GET | `/auth/me` | Профиль (включая компанию и финансы) |
| PATCH | `/auth/me` | Обновить профиль |

### Products

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/products` | Каталог |
| GET | `/products/{code}` | Детали продукта |

### Applications

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/applications` | Создать заявку и запустить обработку |
| GET | `/applications` | Список своих заявок (пагинация) |
| GET | `/applications/{application_id}` | Детали заявки |
| GET | `/applications/{application_id}/events` | История событий |

### Files

Существующий модуль без изменений.

### Admin

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/admin/applications` | Все заявки (только `admin`) |
| GET | `/admin/stats/overview` | Общая статистика по заявкам |

## 8. WebSocket

### Подключение

```
WS /ws/applications?token=<access_token>
```

JWT передаётся в query-параметре (стандарт для WebSocket — заголовки не работают в браузерном API). При невалидном токене — закрытие с кодом 4401.

### Менеджер соединений

Хранит map `user_id → list[WebSocket]`. Позволяет одному пользователю держать несколько соединений (несколько вкладок). При отправке события рассылает всем каналам пользователя.

### Формат сообщений

Сервер → клиент:

```json
{
  "type": "status_changed",
  "application_id": "8a3f9c2e...",
  "status": "confirmed",
  "payload": {
    "score": 712,
    "risk_grade": "B",
    "decision": "approve",
    "reason_codes": [...],
    "explanation": "Заявка одобрена на запрошенных условиях. ..."
  },
  "created_at": "2026-03-15T10:00:01Z"
}
```

```json
{
  "type": "event",
  "application_id": "8a3f9c2e...",
  "event_type": "enriched",
  "payload": {"sources": ["egrul", "fns", "bki"]},
  "created_at": "2026-03-15T10:00:00Z"
}
```

Клиент → сервер сообщений **не отправляет** (только ping/pong для keep-alive, если нужно).

### Гарантии

- Каждое изменение статуса гарантированно отправляется всем соединениям пользователя
- Если пользователь отключился — событие пишется в БД (`ApplicationEventOrm`), при переподключении фронт запрашивает `GET /applications/{id}/events` и восстанавливает состояние
- При статусе заявки, отличном от `pending`, повторная отправка `status_changed` не происходит (идемпотентность)

## 9. Мок-госуслуги

Внутренние эндпоинты бэкенда, имитирующие государственные источники. Требование кейса — все интеграции моковые.

### ЕГРЮЛ / ЕГРИП

`GET /mock/egrul/{inn}`

Возвращает реквизиты юрлица или ИП:

```json
{
  "inn": "7701234567",
  "ogrn": "1027700132195",
  "legal_name": "ООО Ромашка",
  "legal_form": "llc",
  "status": "active",
  "okved": "62.01",
  "okved_description": "Разработка компьютерного программного обеспечения",
  "region": "Москва",
  "registration_date": "2018-04-12T00:00:00Z",
  "employee_count": 25,
  "director": "Иванов Иван Иванович",
  "address": "г. Москва, ул. Тверская, д. 1"
}
```

Если ИНН не найден — `404` с `{"detail": "Организация не найдена"}`.

### ФНС «Прозрачный бизнес»

`GET /mock/fns/{inn}`

Возвращает налоговые данные:

```json
{
  "inn": "7701234567",
  "tax_regime": "УСН",
  "tax_debt_rub": 0,
  "disqualified_persons": false,
  "mass_address": false,
  "mass_director": false,
  "reliability_score": 85,
  "last_reporting_date": "2025-12-31T00:00:00Z"
}
```

### БКИ (бюро кредитных историй)

`GET /mock/bki/{inn}`

Возвращает кредитную историю:

```json
{
  "inn": "7701234567",
  "credit_score": 712,
  "active_obligations_count": 2,
  "total_outstanding_rub": 3000000,
  "monthly_debt_payments_rub": 120000,
  "max_days_past_due_12m": 0,
  "has_current_past_due": false,
  "credit_utilization": 0.35,
  "closed_obligations_count": 4,
  "applications_last_6m": 1,
  "last_update": "2026-03-14T00:00:00Z"
}
```

### Поведение

- Мок-сервисы могут иметь искусственную задержку (`sleep 0.3–1.5s`), чтобы демонстрировать статус `pending`
- Для одной и той же ИНН ответ стабилен (детерминированная генерация по хешу ИНН)
- Для невалидного ИНН — `404`
- При имитации сбоя (`?fail=true`) — `500`, чтобы можно было показать статус `failed`

## 10. Интеграция с ML

МL-сервис уже существует и принимает gRPC `ScoreApplication`. Контракт не меняется.

**Что бэкенд отправляет в ML (из `ScoreApplicationRequest`):**
- `application_id` — сгенерированный бэкендом
- `application` — параметры заявки (product_type, requested_amount_rub, term_months, purpose, segment, submitted_at)
- `company` — реквизиты компании (inn, ogrn, legal_name, legal_form, okved, region, registration_date, employee_count)
- `financials` — финансовые показатели
- `credit_history` — кредитная история

Данные берутся из snapshot заявки (копия профиля пользователя на момент подачи). Мок-обогащение через `enriched_data` может дополнять поля, если в профиле их не было.

**Что бэкенд получает от ML:**
- `score` (0–1000), `pd` (0–1), `risk_grade` (A–E)
- `reason_codes[]` — с готовыми русскими описаниями
- `decision.decision` — `approve` / `approve_with_conditions` / `manual_review` / `decline`
- `decision.reason_codes[]` — коды политики
- `decision.conditions[]` — например `{code: REDUCE_AMOUNT, recommended_amount_rub: 5000000}`
- `explanation` (поле в разработке на стороне ML) — словесный комментарий LLM

Всё это сохраняется в `scoring_result` и `explanation` полях заявки.

## 11. Что НЕ входит в MVP

Перечислено явно, чтобы не возникало вопросов при ревью:

- Пошаговый мастер заявки с черновиками — заявка создаётся одной формой
- Офферы с TTL, принятие/отклонение оффера
- Загрузка документов по запросу банка, задачи на документы, проверка менеджером
- Подписание договора
- Выдача денег
- Сопровождение кредита (график платежей, остаток, просрочки)
- Множественные роли внутри компании (бухгалтер, наблюдатель, поручитель)
- Возможность привязать к одному пользователю несколько компаний
- Андеррайтинг с ручной проверкой (статус `manual_review` из ML мапится в `different`, отдельного экрана нет)
- CRUD продуктов через API (продукты заводятся seed при старте)

## 12. Технические требования к реализации

- Backend: FastAPI, SQLAlchemy async, PostgreSQL, gRPC-клиент к ML-сервису
- Все внешние интеграции — моковые, живут внутри backend под префиксом `/mock/`
- Все статусы меняются через единый сервис `ApplicationService` — никаких прямых `UPDATE` в роутерах
- Каждое изменение статуса пишет `ApplicationEventOrm` **и** отправляет WebSocket-сообщение **в одной транзакции с бизнес-операцией** (сначала БД, потом push; если push упал — событие всё равно в БД)
- Идемпотентность `POST /applications` через заголовок `Idempotency-Key` (опционально, если успеем)
- Все тесты (unit / integration / e2e) должны покрывать:
  - маппинг `decision → status` для всех 5 исходов
  - обогащение через 3 мока + обработку их ошибок
  - WebSocket: подключение, получение события, отключение
  - восстановление состояния после переподключения
  - каталог продуктов: список, детали, seed-идемпотентность