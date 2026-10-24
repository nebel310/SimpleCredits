# AGENTS.md

Единая точка инструкций для AI-агентов (Codex, Cursor, Copilot, Claude Code, Gemini CLI), работающих над проектом SimpleCredits. Перед любой задачей агент обязан прочитать этот файл и следовать правилам.

## 1. Что это за проект

Веб-бэкенд умного кредитного кабинета для малого и микробизнеса (хакатон «Альфа-Будущее 2026»). Пользователь регистрируется, заполняет профиль компании, подаёт кредитную заявку. Бэкенд обогащает данные через моковые государственные сервисы, отправляет их в ML-сервис скоринга по gRPC, получает решение и присваивает заявке финальный статус. Клиент получает обновления статуса в реальном времени через WebSocket.

Полное описание продукта — в `USERFLOW.md`. Если между этим файлом и `USERFLOW.md` есть расхождение по бизнес-логике, приоритет у `USERFLOW.md`. Если расхождение по кодстайлу и техническим правилам — приоритет у этого файла.

## 2. Стек

- Python 3.12, `uv` для зависимостей и виртуального окружения
- FastAPI + uvicorn (async)
- PostgreSQL 17 + SQLAlchemy 2.0 async + asyncpg
- MinIO (S3) через `aiobotocore`
- gRPC (клиент) для взаимодействия с ML-сервисом
- Docker Compose
- pytest, pytest-asyncio, pytest-cov, httpx, aiosqlite (для тестов)

## 3. Структура проекта

```
backend/
├── ml_grpc/              gRPC-клиент ML-сервиса
│   ├── client.py         ScoringClient
│   ├── exceptions.py     доменные исключения
│   ├── mappers.py        proto ↔ Pydantic
│   └── generated/        сгенерированные стабы (не править руками)
├── minio/                S3-клиент
│   ├── client.py         S3Client
│   └── exceptions.py
├── models/               SQLAlchemy-модели
│   ├── auth.py           UserOrm, RefreshTokenOrm, BlacklistedTokenOrm
│   ├── files.py          FileOrm
│   ├── products.py       ProductOrm
│   └── applications.py   ApplicationOrm, ApplicationEventOrm
├── repositories/         доступ к БД
│   ├── auth.py           UserRepository
│   ├── files.py          FileRepository
│   ├── products.py       ProductRepository
│   └── applications.py   ApplicationRepository
├── router/               HTTP-слой
│   ├── auth.py
│   ├── files.py
│   ├── products.py
│   ├── applications.py
│   ├── mock.py           мок-госуслуги
│   ├── admin.py
│   └── ws.py             WebSocket
├── schemas/              Pydantic-схемы
│   ├── base.py
│   ├── auth.py
│   ├── files.py
│   ├── products.py
│   └── applications.py
├── services/             бизнес-логика над репозиториями
│   ├── enrichment.py     обогащение через мок-источники
│   ├── scoring.py        маппинг decision → status
│   └── ws_manager.py     менеджер WebSocket-соединений
├── utils/
│   ├── pagination.py     курсоры
│   └── security.py       JWT, пароли, зависимости ролей
├── tests/
│   ├── conftest.py       общий (SQLite in-memory + патч bcrypt)
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── database.py           engine, new_session, Model
├── main.py               FastAPI app, lifespan, роутеры
├── pyproject.toml
├── uv.lock
├── Dockerfile
└── Makefile
```

## 4. Кодстайл (обязательно)

### Комментарии и докстринги

- Комментарии через `#` **запрещены**, кроме служебных директив (`# noqa: E402`) и кода, сгенерированного protoc
- Под каждой функцией, классом, методом — докстринг
- Докстринг в одну строку, кратко, без точки в конце
- Язык докстрингов — русский

```python
class UserRepository:
    """Репозиторий для работы с пользователями"""

    @classmethod
    async def get_user_by_email(cls, email: str) -> UserOrm | None:
        """Возвращает пользователя по email или None"""
        ...
```

### Отступы и форматирование

- Между функциями, классами и логическими блоками внутри функции — две пустые строки
- Один пустой перевод строки между импортами разных групп (stdlib, third-party, local)
- Длина строки — до 100 символов
- Никаких `from __future__ import annotations` — проект на Python 3.12, `X | Y` работает нативно

### Именование

| Сущность | Суффикс / префикс | Пример |
|---|---|---|
| Модель SQLAlchemy | `Orm` | `UserOrm`, `ApplicationOrm` |
| Pydantic-схема | префикс `S` | `SUser`, `SScoreApplicationRequest` |
| Схема-ответ | суффикс `Response` | `RegisterResponse`, `SApplicationListResponse` |
| Репозиторий | суффикс `Repository` | `UserRepository`, `ApplicationRepository` |
| Сервис | суффикс `Service` | `ScoringService`, `EnrichmentService` |
| Кастомная ошибка | суффикс `Error` | `StorageError`, `GrpcUnavailableError` |

Методы репозиториев — `async @classmethod`, кроме случаев, когда нужен `self` (у нас таких нет).

### Async

- Везде, где есть I/O — `async/await`
- Никаких блокирующих вызовов в async-функциях, кроме `asyncio.to_thread` для CPU-bound или legacy-библиотек (например, `python-magic`)
- Сессии БД открываются через `async with new_session() as session:` — на каждый метод репозитория

### Ошибки

- Кастомные исключения живут в `*/exceptions.py` рядом с модулем, который их кидает
- Роутеры конвертируют доменные исключения в `HTTPException` с корректными статусами
- Никогда не ловить `Exception` без повторного `raise` или явной обработки
- Не глотать ошибки молча

### Валидация

- Вся валидация входных данных — на уровне Pydantic-схем
- Бизнес-правила — на уровне сервисов
- В роутерах — только вызов сервиса и маппинг исключений в HTTP-статусы

### Enum'ы и строковые значения

- В БД и Pydantic — строковые значения (`"confirmed"`, `"different"`), не int-enum'ы
- В ML (proto) — int-enum'ы, маппинг между ними через словари в `ml_grpc/mappers.py`
- Никаких магических строк в коде — выносить в константы модуля при первом использовании больше одного раза

### Зависимости

- Добавлять только через `uv add` / `uv add --dev`
- `uv.lock` коммитится
- Версии ML-зависимостей (`grpcio`, `protobuf`) синхронизированы с ML-сервисом

### Генерация кода

- Никогда не редактировать `ml_grpc/generated/` руками
- Стабы генерятся командой `make proto` из `proto/simplecredits/scoring/v1/scoring.proto`

## 5. Тесты

### Обязательное покрытие

Для каждой новой функции — три группы кейсов:

1. Позитивный (happy path)
2. Негативный (невалидные входные данные, ошибки внешних сервисов)
3. Corner case (пустые списки, граничные значения, `null`, дубликаты)

Цель — 100% покрытие по коду, который содержит бизнес-логику (`services/`, `repositories/`, `ml_grpc/mappers.py`, `utils/`). Роутеры и модели — по мере возможности, но через integration/e2e.

### Уровни

- `tests/unit/` — без БД, без сети. Всё через `monkeypatch` и `AsyncMock`. Быстро (< 5 секунд на весь каталог).
- `tests/integration/` — с SQLite in-memory через фикстуру `db_schema`. Проверяют репозитории и роутеры с in-process gRPC-сервером.
- `tests/e2e/` — сквозные сценарии через `httpx.ASGITransport` с настоящим `app` из `main.py`. Проверяют полный пользовательский путь.

### Правила написания

- Один тест — одна проверяемая ситуация
- Название теста: `test_<что>_<при_каком_условии>_<результат>`
- Докстринг в одну строку на русском, без точки
- Фикстуры — в `conftest.py` соответствующего уровня
- Никаких `time.sleep` в тестах
- Все тесты должны быть изолированы: порядок запуска не влияет на результат

### Запуск

```bash
make test-unit          # только unit
make test-integration   # только integration
make test-e2e           # только e2e
make test               # все
make test-cov           # все с покрытием
```

## 6. Инфраструктура

### Docker Compose

Все сервисы в одном `docker-compose.yml`:

- `db` — PostgreSQL 17
- `minio` — S3-совместимое хранилище (образ `pgsty/silo` или `bitnami/minio`, не `minio/minio` — официальный образ недоступен с сентября 2026)
- `ml` — ML-сервис скоринга (gRPC, порт 50051, наружу не публикуется)
- `backend` — FastAPI

`docker compose up -d --build` поднимает всё. `backend` ждёт healthcheck всех остальных.

### Переменные окружения

Все секреты и конфиги — через `.env`. Файл `.env.example` содержит все ключи с дефолтными значениями. Новые переменные добавлять в оба файла.

### База данных

- В dev — `create_all` при старте (см. `lifespan` в `main.py`)
- Миграции (Alembic) в MVP не используются; при изменении схемы в dev — дропать таблицы и создавать заново
- В `lifespan` при `DEBUG=true` можно вызывать `delete_tables()` для сброса

## 7. Правила взаимодействия с ML

- Proto-контракт — источник истины, лежит в `proto/simplecredits/scoring/v1/scoring.proto`
- Все изменения контракта — сначала в proto, потом `make proto` в backend и в ML
- Никакой бизнес-логики в `ml_grpc/client.py` — только транспорт и маппинг ошибок
- Маппинг `decision → status` живёт в `services/scoring.py`, не в клиенте

## 8. План разработки

Идём фазами. Каждая фаза — это отдельный PR с зелёными тестами.

### Фаза 0 — готово

- Аутентификация (регистрация, логин, refresh, logout)
- Профиль пользователя (GET/PATCH `/auth/me`)
- Загрузка/скачивание файлов (MinIO)
- gRPC-клиент к ML-сервису + мапперы
- Базовый скоринг (`POST /scoring/applications`)
- Тесты: 142 unit + 33 integration + 13 e2e

### Фаза 1 — модели и продукты

1. Расширить `UserOrm` полями компании, финансов и кредитной истории
2. Создать `ProductOrm` в `models/products.py`
3. Создать `ApplicationOrm`, `ApplicationEventOrm` в `models/applications.py`
4. `repositories/products.py` с `ensure_products` (идемпотентный seed)
5. Вызвать `ensure_products` в `lifespan`
6. `GET /products`, `GET /products/{code}`
7. Тесты: unit на схемы, integration на репозиторий, e2e на эндпоинты

### Фаза 2 — мок-госуслуги

1. `router/mock.py` с тремя эндпоинтами: `/mock/egrul/{inn}`, `/mock/fns/{inn}`, `/mock/bki/{inn}`
2. Детерминированная генерация ответов по хешу ИНН
3. Искусственная задержка 0.3–1.5s + параметр `?fail=true` для симуляции сбоя
4. `services/enrichment.py` — параллельные вызовы трёх источников через `asyncio.gather`, сборка в `enriched_data`
5. Тесты: unit на детерминизм генераторов, integration на оба слоя

### Фаза 3 — новая заявка и статусы

1. `services/scoring.py` — маппинг `decision → status` по правилам из USERFLOW.md раздел 5
2. `services/application.py` — оркестратор: создать заявку → обогатить → отправить в ML → сохранить результат → сменить статус → записать событие → отправить WS
3. `repositories/applications.py` — CRUD
4. `POST /applications` — запускает оркестратор, возвращает 201 с заявкой
5. `GET /applications`, `GET /applications/{id}`, `GET /applications/{id}/events`
6. Отдельно: старый `POST /scoring/applications` удалить или переименовать в deprecated, чтобы не дублировать логику
7. Тесты: unit на статус-маппер, integration на оркестратор, e2e на полный путь

### Фаза 4 — WebSocket

1. `services/ws_manager.py` — менеджер соединений `user_id → list[WebSocket]`
2. `WS /ws/applications?token=<jwt>` — принимает соединение, валидирует токен, держит открытым
3. Интеграция с оркестратором: при смене статуса — пуш всем соединениям пользователя
4. Тесты: unit на менеджер, e2e на полный путь с WS-клиентом

### Фаза 5 — админ-слой

1. `utils/security.py` — `require_admin = require_role("admin")`
2. `router/admin.py` — `GET /admin/applications`, `GET /admin/stats/overview`
3. `main.py` — `ensure_admin` в `lifespan` (данные из env)
4. Тесты: unit на роль-гейт, e2e на доступ

### Фаза 6 — финальная полировка

1. Swagger (`custom_openapi`) — все защищённые эндпоинты в `secured_paths`
2. `README.md` с инструкцией запуска и описанием архитектуры
3. `THIRD_PARTY_NOTICES.md`
4. Проверка всех e2e-сценариев из USERFLOW.md раздел 6
5. Покрытие тестами 100%

## 9. Ограничения

### Что НЕ делать

- **Не добавлять новые микросервисы** кроме уже существующего ML. Всё остальное — модули внутри backend.
- **Не добавлять Kafka, RabbitMQ, Celery, Redis, Elasticsearch.** Обычная очередь задач не нужна, WebSocket закрывает требования realtime.
- **Не добавлять Alembic** в MVP. Схема живёт через `create_all`, при изменениях — дроп и пересоздание.
- **Не использовать Django/DRF.**
- **Не реализовывать** офферы с TTL, подписание, выдачу, сопровождение кредита, документы-задачи, множественные компании на пользователя — это всё явно вне MVP (см. USERFLOW.md раздел 11).
- **Не редактировать** `ml_grpc/generated/` руками.
- **Не коммитить** секреты, `.venv`, `.env`, `__pycache__`, `.pytest_cache`.

### Что делать обязательно

- Каждое изменение в коде сопровождается тестами на трёх уровнях (unit, integration, e2e)
- Каждое изменение схемы БД проверяется на SQLite через фикстуру `db_schema` (кидает `drop_all` перед каждым тестом)
- Смена статуса заявки — только через `services/application.py`, никаких прямых `UPDATE` в роутерах
- Событие `ApplicationEventOrm` пишется в той же транзакции, что и бизнес-операция
- WS-пуш отправляется после коммита БД, не до
- Логирование — только в `lifespan` и в точках, где важен мониторинг (старт, остановка, ошибки интеграций)

## 10. Частые ошибки (на что обращать внимание при ревью)

- Забыли `await` в async-функции → тест проходит, но код работает неправильно
- Использовали `datetime.now()` без `tzinfo=timezone.utc` → в БД попадает naive-дата, при чтении на другом хосте сдвиг
- Вернули `ORM`-объект из роутера вместо `Pydantic`-схемы → SQLAlchemy детачит объект, поля теряются
- Забыли `await session.commit()` → изменения не сохраняются
- Оставили `# комментарий` → нарушение кодстайла
- Добавили `field(example=...)` вместо `json_schema_extra={"example": ...}` → pydantic-deprecation-warning
- Прямой вызов `new_session()` из роутера → бизнес-логика должна быть в сервисе
- Голый `except Exception` без специфичной обработки → скрывает баги

## 11. Контакты и ссылки

- `USERFLOW.md` — полное описание продукта и бизнес-логики
- `proto/simplecredits/scoring/v1/scoring.proto` — контракт ML-сервиса
- `openapi.yaml` — актуальная спецификация HTTP API (для фронтенда)
- `ml/` — ML-сервис (отдельный репозиторий-модуль, изменения только через proto)