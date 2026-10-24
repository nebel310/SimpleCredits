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

- создаёт таблицы (`create_all`)
- создаёт бакет MinIO (`ensure_bucket`)
- засеивает продукты (`ensure_products`, идемпотентно)
- создаёт админа из env (`ensure_admin`)

Если менялась схема БД (миграций нет) — **пересоздать volume**:

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
| POST | `/auth/refresh` | Обновить access-токен |
| POST | `/auth/logout` | Выход |
| GET | `/auth/me` | Профиль (включая компанию/финансы/КИ) |
| PATCH | `/auth/me` | Обновить профиль |
| GET | `/products` | Каталог продуктов |
| GET | `/products/{code}` | Детали продукта |
| POST | `/applications` | Создать заявку (обогащение → ML → статус) |
| GET | `/applications` | Свои заявки (пагинация) |
| GET | `/applications/{id}` | Детали заявки |
| GET | `/applications/{id}/events` | История событий |
| POST | `/scoring/batch` | Пакетный скоринг (без сохранения) |
| GET | `/scoring/model-info` | Информация о ML-модели |
| GET | `/admin/applications` | Все заявки (admin) |
| GET | `/admin/stats/overview` | Агрегаты (admin) |
| GET | `/mock/egrul/{inn}` | Мок ЕГРЮЛ (`?fail=true` → 500) |
| GET | `/mock/fns/{inn}` | Мок ФНС (`?fail=true` → 500) |
| GET | `/mock/bki/{inn}` | Мок БКИ (`?fail=true` → 500) |
| WS | `/ws/applications?token=<jwt>` | Обновления статусов |

Полная OpenAPI-спека — в `webdoc.yaml` (Swagger UI: `/docs`).

## Статусы заявки

| Статус | Когда |
|---|---|
| `pending` | Создана, ждём ML |
| `confirmed` | ML `approve` + пользователь выбрал `product_type` |
| `different` | ML `approve_with_conditions` / `manual_review`, или `approve` без `product_type` |
| `declined` | ML `decline` |
| `failed` | Ошибка обогащения / ML / сети |

Маппинг — `services/scoring.decision_to_status`.

## WebSocket

Подключение:

```
ws://localhost:3001/ws/applications?token=<access_token>
```

Невалидный JWT → закрытие с кодом `4401`. Сообщения:

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

См. `USERFLOW.md` §11. Кратко: нет офферов, подписания, выдачи, сопровождения, ручного андеррайтинга, множественных компаний на пользователя.

## Troubleshooting

- `docker compose down -v` при `UNIQUE constraint failed` / `no such table` — схема изменилась
- ML недоступен → заявки получают статус `failed`, ответ `502`
- Мок-госуслуги можно симулировать сбоем: `/mock/egrul/7701234567?fail=true`