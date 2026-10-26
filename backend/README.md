# SimpleCredits — backend умного кредитного кабинета

FastAPI-бэкенд для хакатонного кейса «Альфа-Будущее 2026». Связующее звено между фронтендом, ML-сервисом скоринга (gRPC) и моками госуслуг. Полное описание продукта — в `USERFLOW.md`, правила разработки — в `AGENTS.md`.

## Стек

- Python 3.12, `uv`
- FastAPI + uvicorn
- PostgreSQL 17 + SQLAlchemy 2.0 async + asyncpg
- MinIO (S3) через `aiobotocore`
- gRPC (клиент к ML-сервису)
- pytest + pytest-asyncio + httpx

## Быстрый старт (Docker)

```bash
cp .env.example .env
docker compose up -d --build
```

Сервисы:

- `backend` — http://localhost:3001 (Swagger: `/docs`)
- `db` — PostgreSQL 17, порт 5432
- `minio` — S3, порты 9000 (API), 9001 (console)
- `ml` — gRPC, порт 50051 (наружу не публикуется)

При старте backend:

- создаёт таблицы (`create_all`) и добавляет новые nullable-колонки и индексы в уже существующие (`add_missing_columns`) — база из прошлой версии обновляется без потери данных
- создаёт бакет MinIO (`ensure_bucket`)
- засеивает продукты (`ensure_products`, идемпотентно; при новой `SEED_VERSION` обновляет условия продуктов)
- проставляет `outcome` старым заявкам `different` (`backfill_outcomes`)
- создаёт админа из env (`ensure_admin`)

Если схема поменялась несовместимо (переименование или NOT NULL колонка) — **пересоздать volume**:

```bash
docker compose down -v
docker compose up -d --build
```

## Локальный запуск (без Docker)

```bash
uv sync
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/e2e
```

Для integration/e2e нужен in-memory SQLite (фикстуры из `tests/conftest.py`) — реальные `db`/`minio`/`ml` не требуются.

## Архитектура

```
backend/
├── main.py                 FastAPI app, lifespan, роутеры, custom_openapi
├── database.py             engine, new_session, Model, импорты моделей
├── models/                 SQLAlchemy: auth, files, products, applications
├── repositories/           доступ к БД
├── schemas/                Pydantic-схемы (префикс S)
├── router/                 HTTP-слой и WebSocket
├── services/               бизнес-логика
│   ├── application.py      оркестратор заявки
│   ├── enrichment.py       мок-госуслуги (ЕГРЮЛ/ФНС/БКИ)
│   ├── mock_data.py        детерминированные генераторы
│   ├── scoring.py          decision → status
│   └── ws_manager.py       менеджер WebSocket
├── ml_grpc/                gRPC-клиент ML
├── minio/                  S3-клиент
├── utils/                  pagination, security
└── tests/{unit,integration,e2e}
```

## Ключевые эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/auth/register` | Регистрация |
| POST | `/auth/login` | Вход |
| POST | `/auth/refresh` | Обновить access-токен (тело `{"refresh_token"}` или query) |
| POST | `/auth/logout` | Выход |
| GET | `/auth/me` | Профиль (включая компанию/финансы/КИ) |
| PATCH | `/auth/me` | Обновить профиль |
| GET | `/auth/users` | Пользователи с профилями (admin) |
| GET | `/products` | Каталог продуктов |
| GET | `/products/{code}` | Детали продукта |
| POST | `/applications` | Создать заявку (проверка/подбор продукта → обогащение → ML → решение). Заголовок `Idempotency-Key` |
| GET | `/applications` | Свои заявки (пагинация) |
| GET | `/applications/{id}` | Детали заявки |
| GET | `/applications/{id}/events` | История событий |
| POST | `/applications/{id}/accept` | Принять предложение |
| POST | `/applications/{id}/issue` | Подтвердить и оформить (синтетическая выдача, номер договора) |
| POST | `/applications/{id}/reject` | Отказаться от предложения |
| POST | `/applications/{id}/retry` | Повторить проверку после технической ошибки |
| POST | `/scoring/batch` | Пакетный скоринг (без сохранения) |
| GET | `/scoring/model-info` | Информация о ML-модели |
| GET | `/admin/applications` | Все заявки (admin), фильтры `?status=`, `?outcome=` |
| POST | `/admin/applications/{id}/decision` | Решение по ручной проверке (admin) |
| GET | `/admin/stats/overview` | Агрегаты (admin) |
| GET | `/mock/egrul/{inn}` | Мок ЕГРЮЛ (`?fail=true` → 500) |
| GET | `/mock/fns/{inn}` | Мок ФНС (`?fail=true` → 500) |
| GET | `/mock/bki/{inn}` | Мок БКИ (`?fail=true` → 500) |
| WS | `/ws/applications?token=<jwt>` | Обновления статусов |

Полная OpenAPI-спека — в `webdoc.yaml` (Swagger UI: `/docs`).

## Статусы заявки

| Статус | Когда |
|---|---|
| `pending` | Создана или запущен повтор, ждём ML |
| `confirmed` | ML `approve` + клиент сам выбрал продукт |
| `different` | ML `approve_with_conditions` / `manual_review`, или продукт подобрал банк. Уточнение — `outcome`: `ALTERNATIVE_PRODUCT` / `COUNTER_OFFER` / `MANUAL_REVIEW` |
| `declined` | ML `decline`, отказ банка по ручной проверке или нет подходящего продукта (`NO_SUITABLE_PRODUCT`) |
| `failed` | Ошибка ML / сети, можно повторить (`/retry`) |
| `accepted` | Клиент принял предложение |
| `issued` | Кредит оформлен (синтетическая выдача) |
| `rejected_by_client` | Клиент отказался от предложения |

Маппинг решения модели — `services/scoring.decision_to_status`. Правила банка поверх модели (подбор продукта, оффер со ставкой и платежом, встречное предложение в границах продукта) — `services/products.py` и `services/application.decide_offer`. Принятие и выдача — `services/deal.py`, решение по ручной проверке — `services/bank.py`. Подробно — `USERFLOW.md` §5–6.

## WebSocket

Подключение:

```
ws://localhost:3001/ws/applications?token=<access_token>
```

Невалидный или отозванный (после logout) JWT → закрытие с кодом `4401`. В `status_changed` клиенту уходят только `outcome`, `explanation`, `actions`. Сообщения:

```json
{"type": "status_changed", "application_id": "...", "status": "confirmed", "payload": {...}, "created_at": "..."}
{"type": "event", "application_id": "...", "event_type": "enriched", "payload": {"sources": ["egrul", "fns", "bki"]}, "created_at": "..."}
```

После `disconnect` восстановление — через `GET /applications/{id}/events`.

## Переменные окружения

Полный список — в `.env.example`. Ключевые:

- `DATABASE_URL` — `postgresql+asyncpg://user:pass@host:5432/db`
- `SECRET_KEY`, `ALGORITHM` — JWT
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_BUCKET_NAME`
- `ML_GRPC_HOST`, `ML_GRPC_PORT`, `ML_GRPC_TIMEOUT`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_USERNAME` — создаётся в lifespan

## Тесты

```bash
make test-unit
make test-integration
make test-e2e
make test
make test-cov
```

## Ограничения MVP

См. `USERFLOW.md` §11. Кратко: нет офферов с TTL, загрузки документов по запросу, настоящей подписи и реальной выдачи денег (выдача синтетическая), сопровождения кредита, нескольких компаний на пользователя.

## Troubleshooting

- `docker compose down -v` при `UNIQUE constraint failed` / `no such table` — схема изменилась
- ML недоступен → заявки получают статус `failed`, ответ `502` с `application_id`; после запуска ML — `POST /applications/{id}/retry`
- `python-magic` требует системную библиотеку `libmagic` (в Docker-образе есть; на macOS: `brew install libmagic`)
- Мок-госуслуги можно симулировать сбоем: `/mock/egrul/7701234567?fail=true`