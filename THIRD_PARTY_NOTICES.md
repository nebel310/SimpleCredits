# Сторонние компоненты

Проект использует только бесплатные компоненты с открытыми лицензиями. Платных сервисов, API, моделей и шрифтов нет. LLM не используется. Все данные синтетические.

Лицензии библиотек взяты из метаданных пакетов, версии — из `backend/uv.lock`, `ml/requirements.txt`, `ml/requirements-tracking.txt` и `frontend/package-lock.json`.

## Фронтенд

Полный список с версиями — [frontend/THIRD_PARTY_NOTICES.md](frontend/THIRD_PARTY_NOTICES.md). Ключевые: React, React Router, zustand, Vite (MIT), @alfalab/core-components (MIT, использование согласовано с организаторами), шрифты Onest и Unbounded через @fontsource (SIL OFL 1.1), TypeScript (Apache-2.0).

## Бэкенд — прямые зависимости

| Пакет | Версия | Лицензия |
|---|---|---|
| fastapi | 0.159.1 | MIT |
| starlette | 1.9.0 | BSD-3-Clause |
| uvicorn | 0.54.0 | BSD-3-Clause |
| pydantic, pydantic-core | 2.14.1, 2.50.1 | MIT |
| SQLAlchemy | 2.1.6 | MIT |
| asyncpg | 0.32.0 | Apache-2.0 |
| aiobotocore | 3.9.2 | Apache-2.0 |
| botocore | 1.43.106 | Apache-2.0 |
| grpcio, grpcio-tools | 1.84.1 | Apache-2.0 |
| protobuf | 7.36.2 | BSD-3-Clause |
| googleapis-common-protos | 1.76.0 | Apache-2.0 |
| python-jose | 3.5.0 | MIT |
| passlib | 1.7.4 | BSD |
| bcrypt | 4.0.1 | Apache-2.0 |
| ecdsa | 0.19.2 | MIT |
| rsa | 4.9.1 | Apache-2.0 |
| pyasn1 | 0.6.4 | BSD-2-Clause |
| email-validator | 2.3.0 | Unlicense |
| dnspython | 2.9.0 | ISC |
| python-multipart | 0.0.32 | Apache-2.0 |
| python-magic | 0.4.27 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-dateutil | 2.9.0.post0 | Apache-2.0 или BSD-3-Clause (двойная) |
| aiohttp | 3.14.5 | Apache-2.0 и MIT |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |
| aioitertools | 0.13.0 | MIT |
| aiosignal | 1.4.0 | Apache-2.0 |
| frozenlist | 1.8.0 | Apache-2.0 |
| multidict | 6.9.1 | Apache-2.0 |
| propcache | 0.5.4 | Apache-2.0 |
| yarl | 1.25.1 | Apache-2.0 |
| attrs | 26.1.0 | MIT |
| anyio | 4.15.1 | MIT |
| sniffio | 1.3.1 | MIT или Apache-2.0 |
| h11 | 0.16.0 | MIT |
| idna | 3.20 | BSD-3-Clause |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | BSD |
| greenlet | 3.5.6 | MIT и PSF-2.0 |
| itsdangerous | 2.2.0 | BSD |
| jmespath | 1.1.0 | MIT |
| six | 1.17.0 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| annotated-types | 0.8.0 | MIT |
| urllib3 | 2.8.0 | MIT |
| wrapt | 2.5.1 | BSD-2-Clause |

Для тестов (группа `dev`, в образ не входит): pytest, pytest-asyncio, pytest-cov, httpx, aiosqlite, websockets.

## ML

| Пакет | Версия | Лицензия |
|---|---|---|
| numpy | 2.5.4 | BSD-3-Clause (включает компоненты под 0BSD, MIT, Zlib, CC0-1.0) |
| pandas | 3.1.0 | BSD-3-Clause |
| scipy | 1.18.1 | BSD |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| joblib | 1.6.0 | BSD-3-Clause |
| catboost | 1.2.10 | Apache-2.0 |
| grpcio, grpcio-tools, grpcio-health-checking | 1.84.1 | Apache-2.0 |
| protobuf | 7.36.2 | BSD-3-Clause |
| mlflow-skinny (трекинг экспериментов, ставится в образ) | 3.17.2 | Apache-2.0 |
| pytest (только тесты) | 9.1.1 | MIT |

Модель обучается на синтетических данных при сборке образа; готовые модели и данные третьих сторон не используются.

## Образы Docker

| Образ | Лицензия | Для чего |
|---|---|---|
| `postgres:17.2` | PostgreSQL License | база данных |
| `pgsty/silo` | AGPL-3.0-or-later | S3-хранилище (форк MinIO), используется без изменений как отдельный сервис |
| `python:3.12-slim` | PSF-2.0 (Python), образ на Debian | бэкенд и ML |
| `ghcr.io/astral-sh/uv` | MIT или Apache-2.0 | установка зависимостей бэкенда при сборке |
| `node:20-alpine` | MIT (Node.js) | сборка фронтенда |
| `nginx:1.27-alpine` | BSD-2-Clause | раздача статики фронтенда |
