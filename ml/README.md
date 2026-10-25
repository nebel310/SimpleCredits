# SimpleCredits ML

ML-сервис кредитного скоринга для конвейера SimpleCredits. Сервис обучает модели вероятности дефолта (PD), скорит кредитные заявки, формирует reason-коды и выносит политические решения (approve / conditions / review / decline). Внешний интерфейс — gRPC (`simplecredits.scoring.v1.ScoringService`).

## Содержание

- [Архитектура](#архитектура)
- [Структура проекта](#структура-проекта)
- [Данные](#данные)
  - [Схема признаков](#схема-признаков)
  - [Генератор синтетических данных](#генератор-синтетических-данных)
  - [Point-in-time пайплайн обучения](#point-in-time-пайплайн-обучения)
- [Фичи](#фичи)
- [Модели](#модели)
  - [Линейный скоркард (LogisticRegression)](#линейный-скоркард-logisticregression)
  - [CatBoost](#catboost)
  - [Артефакт модели](#артефакт-модели)
- [Скоринг](#скоринг)
  - [PD → score / risk grade](#pd--score--risk-grade)
  - [Reason-коды](#reason-коды)
  - [Политика решений](#политика-решений)
- [gRPC-сервис](#grpc-сервис)
  - [Протокол](#протокол)
  - [Обработка запроса](#обработка-запроса)
  - [Запуск](#запуск)
  - [Демо-клиент](#демо-клиент)
- [Эксперименты (MLflow)](#эксперименты-mlflow)
- [Docker](#docker)
- [Интеграция с backend](#интеграция-с-backend)
- [Тесты](#тесты)
- [CLI-команды](#cli-команды)
- [Переменные окружения](#переменные-окружения)

## Архитектура

```
                    ┌─────────────────────────────────────────────────────┐
                    │                     ml/                             │
                    │                                                     │
 raw SQLite ──────► │  data/pipeline.py ──► training_table.csv            │
 data/raw/*.db      │  (point-in-time, raw-as-of-v3)                      │
                    │        │                                            │
 generator.py ─────►│        ▼                                            │
 (synthetic)        │  features/features.py ──► обучение (train.py /      │
                    │                            catboost.py)             │
                    │        │                       │                    │
                    │        ▼                       ▼                    │
                    │  scoring/model.py ◄──── artifacts/*.joblib          │
                    │   ├─ PD, score, risk grade                          │
                    │   ├─ scoring/reasons.py (объяснения)                │
                    │   └─ scoring/policy.py (решение)                    │
                    │        │                                            │
 backend ──gRPC───► │  serving/server.py (:50051)                         │
                    │        │                                            │
                    │        └──► tracking/ (MLflow: логи, сравнение)     │
                    └─────────────────────────────────────────────────────┘
```

Путь одной заявки: backend собирает `ScoreApplicationRequest` → gRPC-сервер переводит proto в «сырую» строку признаков → `build_features()` считает производные фичи → модель предсказывает PD → определяются score, risk grade, reason-коды → `evaluate_policy()` выносит решение → ответ уходит в backend.

## Структура проекта

```
ml/
├── src/simplecredits/
│   ├── ml/
│   │   ├── config.py              # имена эксперимента/модели/датасета MLflow
│   │   ├── data/
│   │   │   ├── schema.py          # списки признаков, дефолты, нормализация строки
│   │   │   ├── generator.py       # генератор синтетического датасета
│   │   │   ├── pipeline.py        # point-in-time сборка training table из raw DB
│   │   │   └── raw_features.py    # ~170 расширенных признаков из ~60 raw-таблиц
│   │   ├── features/features.py   # производные фичи, клиппинг, лог-преобразования
│   │   ├── scoring/
│   │   │   ├── model.py           # CreditScorer: загрузка артефакта, PD → score/grade
│   │   │   ├── reasons.py         # reason-коды для logreg и CatBoost
│   │   │   └── policy.py          # правила принятия решений
│   │   ├── serving/server.py      # gRPC-сервер + health checks
│   │   ├── training/
│   │   │   ├── train.py           # линейный скоркард
│   │   │   └── catboost.py        # градиентный бустинг
│   │   └── tracking/
│   │       ├── runner.py          # обёртка над MLflow (run, dataset digest, артефакты)
│   │       ├── pyfunc.py          # MLflow pyfunc-обёртка CreditScorer
│   │       └── compare.py         # сравнение прогонов по метрикам
│   └── scoring/v1/                # сгенерированные protobuf-стабы (scoring_pb2*)
├── scripts/
│   ├── generate_proto.py          # генерация стабов из proto/
│   └── demo_client.py             # демо: скоринг example-заявок по gRPC
├── tests/                         # 30 тестов: unit + e2e gRPC
├── artifacts/                     # обученные модели (*.joblib)
├── data/                          # training_table.csv, синтетические данные
├── mlruns/                        # локальный MLflow-трекинг
└── Dockerfile
```

Требования: Python ≥ 3.12. Зависимости зафиксированы в `pyproject.toml` (numpy, pandas, scikit-learn, catboost, grpcio, protobuf; MLflow — опциональный extra `tracking`).

## Данные

### Схема признаков

Центральный модуль — `data/schema.py`:

- `BASE_NUMERIC_FEATURES` — 22 базовых числовых признака из заявки и кредитной истории (возраст компании, выручка, долг, просрочки, утилизация кредита и т.д.) плюс 18 признаков из налоговых/судебных/транзакционных источников (`tax_debt_rub`, `bki_credit_score`, `txn_inflow_90d`, …).
- `NEW_NUMERIC_FEATURES` — ~170 расширенных признаков: учредители и менеджмент, ЕГРЮЛ/СМЭР, налоговые и СФР-отчёты, бухгалтерская и управленческая отчётность, счета и транзакции, валютные операции, продукты банка, БКИ-кредиты, суды/ФССП/банкротства, залог, лицензии, тендеры, страхование, телематика, маркетплейсы, ОФД, склад, HR, логистика, сайт/репутация/соцсети, история отношений с банком, документы и аудит, биометрия заявителя.
- `RAW_NUMERIC_FEATURES = BASE + NEW` — полный список числовых признаков.
- `CATEGORICAL_FEATURES` — `product_type`, `purpose`, `company_segment`, `legal_form`, `tax_regime`, `client_rating`.
- `DEFAULT_RAW_ROW` — дефолтная «сырая» строка: любые пропущенные признаки заполняются разумными значениями, поэтому сервис устойчив к неполным данным.
- `normalize_raw_row()` приводит произвольный dict к полной схеме (дефолты + типы).

### Генератор синтетических данных

`data/generator.py` создаёт датасет заявок с целевой переменной `default` по заданному сиду — используется для обучения без реальных данных и в тестах:

```bash
python -m simplecredits.ml.data.generator --out data/synthetic_applications.csv --samples 20000 --seed 42
```

### Point-in-time пайплайн обучения

`data/pipeline.py` (версия `raw-as-of-v3`) собирает обучающую таблицу из сырой SQLite-базы `data/raw/simplecredits_raw.db` (генерируется `tools/rawdata/generator.py` в корне репозитория):

```bash
python -m simplecredits.ml.data.pipeline --db data/raw/simplecredits_raw.db \
    --out data/training_table.csv --horizon-days 30
```

Ключевые принципы:

- **Point-in-time корректность.** Для каждой заявки все признаки берутся строго «на момент подачи» (`submitted_at`): `raw_features.py` задаёт для каждой из ~60 таблиц as-of-колонку (`TABLE_AS_OF_COLUMNS`), а пайплайн фильтрует строки по `date < as_of`. Утечки будущего нет.
- **Лейбл.** `default = 1`, если в горизонте наблюдения (`horizon_days`, по умолчанию 30) после подачи произошло событие дефолта по этой заявке (`loan_default_events`, матчинг по `application_id`) или банкротство компании. Событие фиксируется вместе с меткой времени (`label_event`, `label_event_at`).
- **Цензурирование.** Заявки, горизонт которых ещё не созрел к `dataset_cutoff`, исключаются (счётчик `censored_applications` в отчёте).
- **Отбор заявок.** В обучение попадают только заявки в одобренных статусах: `approved`, `offer_sent`, `offer_accepted`, `issued`, `disbursed`, `active`.
- **Отчёт и манифест.** Рядом с CSV пишется `*.manifest.json`: версия пайплайна, SHA-256 базы, количество заявок, горизонт, дата cutoff. Перед сохранением таблица проходит валидацию (`_validate_training_frame`): бинарный таргет, конечные числовые признаки, корректные временные метки.

Расширенные признаки (`raw_features.py`) агрегируются из таблиц-источников: учредители/менеджеры, согласия, ЕГРЮЛ, СМЭР, налоговые и СФР-отчёты, Росстат, бухгалтерия, счета и транзакции, БКИ, суды, приставы, банкротства, имущество, лицензии, тендеры, страхование, телематика, HR, логистика, маркетплейсы, ОФД, сайт, репутация, соцсети, новости, история банка (заявления, скоринги, офферы, контракты), документы, аудит, биометрия.

## Фичи

`features/features.py` преобразует «сырую» строку в вектор модели:

- **Отношения**: `debt_to_revenue`, `debt_service_ratio`, `requested_to_annual_revenue`, `profitability`, `closed_obligations_ratio` и др. Знаменатели клипятся от деления на ноль, отношения ограничены сверху/снизу.
- **Лог-преобразования** (`LOG_FEATURES`): денежные величины (`tax_debt_rub`, `court_claims_rub`, транзакционные потоки и остатки, `total_outstanding`) через signed-log `sign(x)·log1p(|x|`), чтобы тяжёлые хвосты не ломали масштаб.
- **Клиппинг счётчиков** (`EXTRA_COUNT_FEATURES`): например `txn_count_90d ≤ 100 000`, `court_cases_count ≤ 100`; `bki_credit_score` ограничен диапазоном 300–900.
- **Расширенные признаки**: все `NEW_NUMERIC_FEATURES` очищаются от ±inf/NaN и клипятся диапазоном ±10⁶.
- **Категориальные** признаки проходят one-hot (logreg) или нативную обработку (CatBoost).

Итоговый набор — `FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES`; порядок колонок фиксируется в артефакте модели.

## Модели

### Линейный скоркард (LogisticRegression)

`training/train.py`, версия `scorecard-linear-v1`. Baseline: на данных пайплайна проигрывает CatBoost (0.7367 против 0.7753 AUC на одинаковых групповых сплитах), но остаётся объяснимой линейной моделью и используется как fallback, если артефакт CatBoost недоступен.

- sklearn `Pipeline`: `ColumnTransformer` (StandardScaler для числовых, OneHotEncoder для категориальных) + `LogisticRegression` (`C = 0.003`, сильная L2-регуляризация — 170+ признаков при относительно небольшом числе событий легко переобучаются).
- Метрики: ROC-AUC (train/test), Brier score, confusion matrix, кривая покрытия по риск-грейдам, распределение политических решений.

```bash
simplecredits-train --data data/training_table.csv --out artifacts/model.joblib
# или на синтетике:
simplecredits-train --samples 20000 --seed 42 --out artifacts/model.joblib --no-tracking
```

### CatBoost

`training/catboost.py`, версия `catboost-v2` — боевая модель.

Параметры: 250 итераций, `depth = 3`, `lr = 0.03`, `l2_leaf_reg = 10`. Категориальные признаки передаются нативно (`cat_features`); reason-коды считаются через SHAP-вклады CatBoost.

**Методология подбора** (зафиксирована в комментариях к `CATBOOST_PARAMS`):

- **Сплит групповой по `company_id`.** Одна компания целиком попадает либо в train, либо в test. При случайном сплите 618 компаний оказывались в обеих частях, и модель запоминала компанию вместо сигнала.
- **Сетка** `depth` × `l2_leaf_reg` × `learning_rate` просеяна GroupKFold(5) CV; оптимум — `depth=3, l2=10, lr=0.03` (CV AUC 0.7600).
- **Число итераций выбрано по CV-кривой** (100/150/200/250/300/400/600), плато на 250.
- **Early stopping отключён намеренно.** Валидация, вырезанная из train, слишком мала (~75 позитивов), из-за чего `best_iteration` скачет от 19 до 323 между сплитами. Замер по 5 групповым сплитам: early stopping даёт 0.7620 против 0.7753 у фиксированных 250 итераций.

**Качество на held-out групповом тесте** (1361 заявка, 101 дефолт, 0 пересекающихся компаний):

| Метрика | Значение |
|---|---|
| ROC-AUC | 0.7868 (по 5 сидам: 0.7725 ± 0.0152) |
| Gini | 0.5736 |
| KS | 0.4744 |
| Brier | 0.0638 |

Риск-грейды хорошо разделены и откалиброваны: A 0.0% → B 2.1% → C 10.4% → D 17.0% → E 28.6% фактических дефолтов.

CatBoost выбран не произвольно: на одинаковых групповых сплитах он выигрывает у линейного скоркарда на всех 5 сидах (0.7753 против 0.7367 в среднем).

```bash
# на данных пайплайна (путь боевой модели):
simplecredits-catboost --data data/training_table.csv --out artifacts/catboost_model.joblib

# на синтетике (сплит автоматически стратифицированный случайный — в ней нет company_id):
simplecredits-catboost --samples 20000 --seed 42 --no-tracking
```

Метаданные артефакта содержат `training.split` (`grouped_by_company` или `stratified_random`) и `training.n_companies`, чтобы способ обучения был воспроизводим.

### Артефакт модели

Обе команды сохраняют joblib-словарь единого формата, который понимает `CreditScorer`:

```python
{
  "model_type": "logistic_scorecard" | "catboost",
  "model_version": "scorecard-linear-v1",
  "model" | "pipeline": ...,        # CatBoost-модель или sklearn Pipeline
  "feature_columns": [...],         # порядок фичей, зафиксированный при обучении
  "metrics": {...},                 # AUC, Brier и пр.
  "trained_at": "…",
  "training": {...},                # параметры обучения, source данных
}
```

## Скоринг

`scoring/model.py` — класс `CreditScorer`, единая точка инференса для обеих моделей:

```python
scorer = CreditScorer.load("artifacts/model.joblib")
result = scorer.score(raw_row)   # ScoreResult: score, pd, risk_grade, reasons, model_version, policy
```

Входной `raw_row` — произвольный словарь; пропуски заполняются через `normalize_raw_row()` (дефолты из `schema.py`).

### PD → score / risk grade

- `score = round((1 − PD) · 1000)`, ограничен [0, 1000].
- Риск-грейды по PD: **A** < 0.02, **B** < 0.05, **C** < 0.10, **D** < 0.20, иначе **E**.

### Reason-коды

`scoring/reasons.py` объясняет оценку топ-K (по умолчанию 5) вкладов признаков:

- **logreg**: вклад = коэффициент × значение стандартизованного признака; для каждого признака заданы человекочитаемые описания позитивного/негативного влияния (например `BUSINESS_AGE`: «Молодой бизнес без длительной истории» / «Зрелый бизнес с устойчивой историей»).
- **CatBoost**: SHAP-вклады по признакам.

Каждый reason-code содержит `code`, `description`, `feature`, `impact` (positive/negative/neutral) и числовой `contribution`.

### Политика решений

`scoring/policy.py` — детерминированные правила поверх PD и сырых полей (порядок проверки):

| Условие | Решение | Reason |
|---|---|---|
| Текущая просрочка (`has_current_past_due`) | `decline` | `CURRENT_PAST_DUE` |
| Просрочка ≥ 60 дней за 12 мес. | `decline` | `SEVERE_PAST_DUE_HISTORY` |
| PD ≥ 0.35 | `decline` | `HIGH_RISK_SCORE` |
| PD ≥ 0.20 | `manual_review` | `RISK_IN_GREY_ZONE` |
| Платёж/выручка > 0.55 | `manual_review` | `HIGH_DEBT_SERVICE_RATIO` |
| Запрос > 0.6 годовой выручки и > 3 млн ₽ | `approve_with_conditions` | `LOAN_TO_REVENUE_REDUCTION` + условие `REDUCE_AMOUNT` с рекомендованной суммой |
| Иначе | `approve` | — |

Политика вычисляется из *сырой* строки (до фичеинжиниринга), поэтому её пороги прозрачны и настраиваются отдельно от модели.

## gRPC-сервис

### Протокол

Контракт — `proto/simplecredits/scoring/v1/scoring.proto` (общий с backend):

```protobuf
service ScoringService {
  rpc ScoreApplication(ScoreApplicationRequest) returns (ScoreApplicationResponse);
  rpc BatchScoreApplications(BatchScoreApplicationsRequest) returns (BatchScoreApplicationsResponse);
  rpc GetModelInfo(GetModelInfoRequest) returns (GetModelInfoResponse);
}
```

- `ScoreApplicationRequest` — заявка: `Application` (продукт, цель, сумма, срок), `Company` (ОКВЭД, регион, дата регистрации, штат), `Financials`, `CreditHistory`, а также расширяющие map-поля `extra_numeric_features` / `extra_categorical_features` — через них backend передаёт любые признаки из расширенной схемы (БКИ-скор, налоги, транзакции, рейтинг клиента и т.д.), не меняя proto.
- `ScoreApplicationResponse` — `score` (0–1000), `pd`, `risk_grade` (A–E), `reason_codes`, `model_version`, `scored_at`, `decision` (решение, reason-коды политики, условия с рекомендованной суммой).
- `GetModelInfo` — версия/тип модели, список фичей, метрики, дата обучения.

Стабы генерируются из proto и коммитятся в `src/simplecredits/scoring/v1/`:

```bash
python scripts/generate_proto.py
```

### Обработка запроса

`serving/server.py`:

1. `request_to_raw_row()` отображает proto в сырую строку: enum'ы продуктов/целей — в строковые значения, ОКВЭД и регион — в риски по справочникам (`OKVED_RISK_BY_PREFIX`, `REGION_RISK_BY_NAME`), дата регистрации — в возраст компании в месяцах.
2. Map-поля валидируются: неизвестные ключи отклоняются с `ValueError` (gRPC `INVALID_ARGUMENT`) — защита от рассинхрона схем backend и ML.
3. `CreditScorer.score()` считает PD, score, grade, reasons и политику; ответ маппится обратно в proto (`to_response()`).
4. Ошибки скоринга возвращаются клиенту как `INVALID_ARGUMENT` с описанием.

Сервер регистрирует стандартный **gRPC health checking** (`grpc.health.v1.Health`) для корневого сервиса и `simplecredits.scoring.v1.ScoringService` — его используют оркестраторы и readiness-пробы.

Если файл модели отсутствует, сервер при старте сам обучает модель на синтетике (`ensure_model()`, 20 000 сэмплов) — удобно для локального запуска и тестов.

### Запуск

```bash
# из папки ml/
simplecredits-scoring --model artifacts/model.joblib --port 50051 --workers 8
# или
python -m simplecredits.ml.serving.server
```

Параметры берутся из env: `MODEL_PATH`, `GRPC_PORT`, `GRPC_WORKERS` (CLI-аргументы приоритетнее).

### Демо-клиент

```bash
python scripts/demo_client.py --addr localhost:50051
```

Прогоняет example-заявки из `examples/*.json` (good/medium/review/bad) через реальный gRPC и печатает score, PD, grade, решение и reason-коды; предварительно вызывает `GetModelInfo`.

## Эксперименты (MLflow)

MLflow — опциональная зависимость (`pip install -e ".[tracking]"`, трек URI по умолчанию `./mlruns`, эксперимент `simplecredits-credit-scoring`).

Команды обучения пишут в MLflow:

- параметры (регуляризация, сид, размер выборки, source данных);
- метрики (AUC train/test, Brier, confusion matrix, распределение решений и грейдов);
- SHA-256 датасета и обученный артефакт;
- модель как **pyfunc** (`tracking/pyfunc.py`) — её можно загружать и скорить без кода репозитория.

Флаги обучения: `--no-tracking` (без MLflow), `--require-tracking` (падать, если трекинг недоступен), `--register-model` + `--alias` (регистрация в Model Registry под именем `simplecredits-credit-scoring`).

Сравнение прогонов:

```bash
simplecredits-compare --metric roc_auc_test --order desc --limit 10 [--json]
```

## Docker

Образ из корня репозитория (`docker build -f ml/Dockerfile .`):

1. ставит зависимости, копирует `proto/` и `ml/src`, генерирует стабы, устанавливает пакет;
2. на этапе сборки обучает модель (`--no-tracking`) в `/app/ml/artifacts/model.joblib`;
3. запускает gRPC-сервер на порту `50051`.

Env по умолчанию: `MODEL_PATH=/app/ml/artifacts/model.joblib`, `GRPC_PORT=50051`, `GRPC_WORKERS=8`. Подменить модель в рантайме можно, смонтировав свой артефакт и переопределив `MODEL_PATH`.

## Интеграция с backend

- Backend подключается к сервису через `backend/ml_grpc/client.py` по адресу из env `ML_GRPC_HOST` (default `ml`), `ML_GRPC_PORT` (default `50051`), `ML_GRPC_TIMEOUT` (default `10.0`).
- Pydantic-схема `SScoreApplicationRequest` (`backend/schemas/applications.py`) зеркалит proto, включая `extra_numeric_features` / `extra_categorical_features` (до 512 ключей каждое).
- `backend/ml_grpc/mappers.py` конвертирует HTTP-модели в proto и обратно; `schema_to_proto_score_request` прокидывает `extra_*` map-поля в proto.
- Обогащение через мок-госуслуги (`services/enrichment.py`) собирает расширенные признаки в `extract_ml_extra_features()`: `bki.credit_score → bki_credit_score`, `fns.tax_debt_rub → tax_debt_rub`, `fns.tax_regime → tax_regime` (с приведением словаря `УСН → usn`). Сервис заявки (`services/application.py`) подставляет их в `scoring_request` перед вызовом ML.

Таким образом внешний REST-клиент отправляет заявку в backend, backend обогащает её через мок-ЕГРЮЛ/ФНС/БКИ и выступает gRPC-клиентом ML-сервиса.

**Почему это важно для качества модели.** `bki_credit_score` — самый весомый признак CatBoost (~49% важности). Без него ML подставляет дефолт схемы (600), и AUC падает с ~0.76 до ~0.55, а ~78% заявок уходит в грейд E. Поэтому обогащение обязано доходить до ML — `test_prod_model.py` и `test_enrichment_service.py::test_extract_ml_extra_features_*` это фиксируют.

Прод-модель — закоммиченный артефакт `artifacts/catboost_model.joblib` (catboost-v2, 207 признаков). Он кладётся в образ при сборке (`ml/Dockerfile`), а не обучается на синтетике; сборка проверяет тип модели и число признаков и падает при несоответствии.

## Тесты

```bash
cd ml
pip install -e ".[dev]"
pytest            # 30 тестов
```

Покрытие: генератор данных, сборка фичей (в т.ч. вырожденные знаменатели), point-in-time пайплайн (лейблы, цензурирование, манифест), обе модели обучения, политика, скоринг, маппинг proto↔row (включая отклонение неизвестных extra-признаков), MLflow-трекинг и **e2e-тест gRPC** (реальный сервер на случайном порту).

## CLI-команды

| Команда | Модуль | Назначение |
|---|---|---|
| `simplecredits-train` | `training/train.py` | обучение линейного скоркарда |
| `simplecredits-catboost` | `training/catboost.py` | обучение CatBoost-модели |
| `simplecredits-scoring` | `serving/server.py` | запуск gRPC-сервера |
| `simplecredits-compare` | `tracking/compare.py` | сравнение MLflow-прогонов |
| `python -m simplecredits.ml.data.pipeline` | `data/pipeline.py` | сборка training table из raw DB |
| `python -m simplecredits.ml.data.generator` | `data/generator.py` | генерация синтетического датасета |
| `python scripts/generate_proto.py` | — | генерация protobuf-стабов |
| `python scripts/demo_client.py` | — | демо-скоринг по gRPC |

## Переменные окружения

| Переменная | По умолчанию | Где используется |
|---|---|---|
| `MODEL_PATH` | `artifacts/catboost_model.joblib` | serving: путь к артефакту модели |
| `GRPC_PORT` | `50051` | serving: порт gRPC |
| `GRPC_WORKERS` | `8` | serving: размер thread pool |
| `MLFLOW_TRACKING_URI` | `./mlruns` | training/tracking: адрес MLflow |
| `ML_GRPC_HOST` | `ml` | backend: хост ML-сервиса |
| `ML_GRPC_PORT` | `50051` | backend: порт ML-сервиса |
| `ML_GRPC_TIMEOUT` | `10.0` | backend: таймаут gRPC-вызова, сек |
