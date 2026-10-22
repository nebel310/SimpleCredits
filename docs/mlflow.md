# MLflow: эксперименты, датасеты и модели

В проекте настроен MLflow для сохранения параметров обучения, метрик, датасетов, весов модели и результатов оценки. Поддерживаются два режима:

- HTTP-сервер MLflow — общий experiment tracking и model registry;
- локальный file store — быстрый офлайн-режим без registry.

## 1. Запуск MLflow-сервера

Из корня репозитория:

```powershell
docker compose -f docker-compose.mlflow.yml up -d
```

Проверка:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:5000/health
```

Веб-интерфейс: http://localhost:5000

Данные сервера сохраняются в `./mlflow/`:

- `mlflow/mlflow.db` — SQLite с экспериментами и registry;
- `mlflow/artifacts/` — артефакты, датасеты и веса моделей.

Остановка:

```powershell
docker compose -f docker-compose.mlflow.yml down
```

Полный сброс сервера — остановить контейнер и удалить каталог `mlflow/`.

Логи:

```powershell
docker compose -f docker-compose.mlflow.yml logs -f mlflow
```

## 2. Установка клиента

Рекомендуется Python 3.12 или 3.13. На Python 3.15 установка `mlflow-skinny` может падать на сборке PyYAML из-за отсутствия wheel.

```powershell
py -3.13 -m venv .venv-mlflow
.\.venv-mlflow\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r ml/requirements.txt -r ml/requirements-tracking.txt
pip install -e ml
```

`mlflow-skinny` — только клиент. MLflow UI и registry запускаются через контейнер.

Если нужно остаться на Python 3.15, PyYAML можно собрать в pure-Python режиме:

```powershell
$env:PYYAML_FORCE_LIBYAML = "0"
pip install pyyaml==6.0.3 --no-build-isolation
pip install -r ml/requirements-tracking.txt
```

## 3. Обучение с логированием

Указать сервер:

```powershell
$env:MLFLOW_TRACKING_URI = "http://localhost:5000"
```

Или передать URI явно:

```powershell
python -m simplecredits.ml.training.train --samples 20000 --run-name baseline
```

Эквивалент через установленный console script:

```powershell
simplecredits-train --samples 20000 --run-name baseline
```

По умолчанию логирование включено. Если MLflow недоступен, обучение продолжается, модель сохраняется локально, а в stderr выводится предупреждение. Поведение меняется флагами:

- `--require-tracking` — завершить обучение с ошибкой, если логирование не удалось;
- `--no-tracking` — не использовать MLflow;
- `--tracking-uri` — переопределить `MLFLOW_TRACKING_URI`;
- `--experiment` — имя эксперимента, по умолчанию `simplecredits-credit-scoring`;
- `--run-name` — имя запуска;
- `--data` — обучить на готовом CSV вместо генератора;
- `--test-size` — доля тестовой выборки;
- `--seed` — seed генератора и разбиения.

Пример на готовом датасете:

```powershell
python -m simplecredits.ml.training.train --data data\applications.csv --run-name custom-data
```

Сгенерированный датасет сохраняется в `ml/data/<digest>.csv` и логируется как артефакт. При `--data` используется указанный файл.

## 4. Регистрация модели и alias

Регистрация доступна только при HTTP tracking URI:

```powershell
python -m simplecredits.ml.training.train --run-name candidate --register-model
```

С alias:

```powershell
python -m simplecredits.ml.training.train --run-name candidate --register-model --alias champion
```

Параметры:

- `--registered-model-name` — имя модели в registry, по умолчанию `simplecredits-credit-scoring`;
- `--alias` — alias версии, например `champion`.

Загрузка зарегистрированной модели:

```python
import mlflow

mlflow.set_tracking_uri("http://localhost:5000")
model = mlflow.pyfunc.load_model("models:/simplecredits-credit-scoring@champion")
predictions = model.predict(frame)
```

Локальный file store registry не поддерживает. При `--register-model` без HTTP URI будет ошибка.

## 5. Сравнение запусков

```powershell
python -m simplecredits.ml.tracking.compare --metric roc_auc_test --limit 10
```

Или после `pip install -e ml`:

```powershell
simplecredits-compare --metric roc_auc_test --limit 10
```

Полезные флаги:

- `--experiment` — имя эксперимента;
- `--metric` — метрика сортировки, по умолчанию `roc_auc_test`;
- `--order asc|desc` — направление сортировки;
- `--limit` — число запусков;
- `--json` — вывести JSON вместо таблицы;
- `--tracking-uri` — URI сервера или локального хранилища.

Таблица содержит `run_id`, `run_name`, `status`, выбранную метрику, ROC-AUC, Brier, approval rate, approved default rate, seed, число объектов и версию модели.

## 6. Что сохраняется в запуске

Параметры и теги:

- версия и тип модели, seed, размеры выборок, default rate, гиперпараметры LogReg;
- версии Python, pandas, scikit-learn, MLflow;
- git commit, digest датасета, tracking schema version.

Метрики:

- ROC-AUC train/test, Gini, KS, Brier, средний PD;
- default rate на тесте;
- approval rate и approved default rate;
- counts/rates по policy-решениям;
- counts по риск-грейдам;
- accuracy, precision, recall, specificity, F1 и confusion matrix на threshold.

Артефакты:

- `data/` — датасет;
- `model_weights/model.joblib` — веса;
- `evaluation/train_predictions.csv`;
- `evaluation/test_predictions.csv`;
- `evaluation/split.csv`;
- `evaluation/metrics.json`;
- `evaluation/policy_summary.json`;
- `evaluation/threshold_metrics.json`;
- `evaluation/risk_grade_counts.json`;
- `evaluation/evaluation.json`;
- `evaluation/model_manifest.json`;
- `evaluation/data_manifest.json`.

Pyfunc-модель сохраняется как `models:/m-...` и доступна во вкладке Models. При регистрации создаётся версия в registry.

## 7. Локальный режим без сервера

```powershell
python -m simplecredits.ml.training.train --samples 2000 --tracking-uri mlruns
```

Если `--tracking-uri` и `MLFLOW_TRACKING_URI` не заданы, используется `mlruns/` в корне репозитория. Для file store автоматически выставляется `MLFLOW_ALLOW_FILE_STORE=true`.

Ограничения локального режима:

- нет model registry;
- нет веб-интерфейса при использовании `mlflow-skinny`;
- `mlflow ui` требует полный пакет `mlflow`, а не `mlflow-skinny`.

Для сравнения локальных запусков:

```powershell
python -m simplecredits.ml.tracking.compare --tracking-uri mlruns
```

## 8. Проверка

Базовые тесты:

```powershell
python -m pytest ml/tests -q
```

Тест MLflow пропускается, если `mlflow` не установлен. В окружении с tracking-зависимостями:

```powershell
python -m pytest ml/tests -q
```

Проверка синтаксиса:

```powershell
python -m compileall -q ml/src ml/tests
```

Проверены сценарии:

- file store: логирование run, метрик, датасета, артефактов, pyfunc-модели и загрузка модели;
- HTTP-сервер MLflow 3.17.2: логирование, регистрация версии, alias `champion`, загрузка модели из registry и предсказание;
- сравнение запусков через CLI по file store и HTTP;
- аргументы запуска MLflow-сервера из compose проверены на локальном сервере.

Docker-контейнер в текущем окружении не запускался: Docker не установлен. Образ `ghcr.io/mlflow/mlflow:v3.17.2` проверен по registry.

## 9. Типичные проблемы

`Model registration requires an MLflow tracking server URI`

Используйте HTTP URI (`http://localhost:5000`), а не `mlruns`.

`MLflow is not installed`

Установите tracking-зависимости:

```powershell
pip install -r ml/requirements-tracking.txt
```

На Python 3.15 см. раздел установки.

Сервер недоступен, но модель нужна

Обучение продолжается без tracking. Чтобы это было ошибкой, используйте `--require-tracking`.

Корпоративный proxy мешает обращениям к localhost

Задайте исключение:

```powershell
$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = "localhost,127.0.0.1"
```

Порт 5000 занят

Измените mapping в `docker-compose.mlflow.yml` и передайте новый URI в `--tracking-uri` или `MLFLOW_TRACKING_URI`.

Нужно удалить эксперименты и registry

Остановите контейнер и удалите `mlflow/`. Каталоги `mlruns/`, `mlartifacts/`, `mlflow.db*` и `mlflow/` исключены из git.
