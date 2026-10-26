"""Гарантии на прод-модель: то, что реально подаёт gRPC-сервер.

Артефакт ml/artifacts/catboost_model.joblib закоммичен намеренно и кладётся в
образ при сборке (ml/Dockerfile). Эти тесты не дают подменить его на другую
модель или на устаревшую версию без явной правки ожиданий.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from simplecredits.ml.features.availability import serving_available_features
from simplecredits.ml.scoring.model import CreditScorer
from simplecredits.ml.serving.server import (
    DEFAULT_CATBOOST_MODEL_PATH,
    request_to_raw_row,
    to_response,
)
from simplecredits.ml.training.catboost import CATBOOST_MODEL_VERSION
from simplecredits.scoring.v1 import scoring_pb2
from google.protobuf.timestamp_pb2 import Timestamp

ML_ROOT = Path(__file__).resolve().parents[1]
PROD_ARTIFACT = ML_ROOT / "artifacts" / "catboost_model.joblib"

MAX_FEATURES = 30
# Минимально приемлемое качество на held-out групповом тесте. Замеренное
# значение 0.7763; порог ниже, чтобы тест не дрожал, но отсекал явный мусор.
MIN_ACCEPTABLE_TEST_AUC = 0.75


@pytest.fixture(scope="module")
def prod_scorer():
    if not PROD_ARTIFACT.exists():
        pytest.skip(f"prod artifact not built yet: {PROD_ARTIFACT}")
    return CreditScorer.load(PROD_ARTIFACT)


def test_default_model_path_points_at_catboost_artifact():
    """Дефолт сервера — CatBoost-артефакт, а не линейный скоркард."""
    assert DEFAULT_CATBOOST_MODEL_PATH == Path("artifacts/catboost_model.joblib")


def test_prod_artifact_is_current_catboost(prod_scorer):
    assert prod_scorer.model_version == CATBOOST_MODEL_VERSION
    assert prod_scorer.model_type == "catboost"
    assert 0 < len(prod_scorer.feature_columns) <= MAX_FEATURES


def test_prod_artifact_uses_only_serving_available_features(prod_scorer):
    """Главный инвариант: модель не опирается на недоступные в проде признаки.

    Признак вне прод-пула в проде всегда равен дефолту схемы, поэтому модель
    подбирает под него веса, которые никогда не отработают. На catboost-v3 это
    дало коллапс: PD всех заявок схлопнулся в 0.23-0.32, все получили грейд E
    и manual_review, ни одного approve.

    Это та же проверка, которую ml/Dockerfile выполняет при сборке образа
    (scripts/verify_prod_model.py).
    """
    off_pool = sorted(set(prod_scorer.feature_columns) - set(serving_available_features()))

    assert off_pool == [], f"model uses features backend cannot supply: {off_pool}"

    selection = prod_scorer.model_info()["training"]["feature_selection"]
    assert selection["restricted_to_serving_available"] is True
    assert set(selection["selected_features"]) == set(prod_scorer.feature_columns)


def test_prod_artifact_records_acceptable_metrics(prod_scorer):
    info = prod_scorer.model_info()
    metrics = info["metrics"]

    assert "roc_auc_test" in metrics
    assert metrics["roc_auc_test"] >= MIN_ACCEPTABLE_TEST_AUC
    assert metrics["roc_auc_test"] <= 1.0

    # Метрики должны считаться на честном сплите: train не обязан равняться
    # test, но train заметно выше — признак того, что сплит не переобучен.
    assert metrics["roc_auc_train"] >= metrics["roc_auc_test"]

    # Артефакт обязан помнить, как его обучили: иначе результат
    # невоспроизводим.
    training = info["training"]
    assert training["split"] == "grouped_by_company"
    assert training["n_companies"] > 1
    assert training["params"]["iterations"] == 250
    assert info["trained_at"]


def test_prod_artifact_scores_realistic_applications(prod_scorer):
    """Хорошая заявка получает меньший PD, чем плохая."""
    good = prod_scorer.score(
        {
            "company_age_months": 96,
            "employee_count": 25,
            "okved_risk": 0.2,
            "region_risk": 0.1,
            "annual_revenue_rub": 120_000_000,
            "monthly_revenue_rub": 10_000_000,
            "monthly_expenses_rub": 8_000_000,
            "total_debt_rub": 3_000_000,
            "requested_amount_rub": 1_500_000,
            "term_months": 24,
            "monthly_debt_payments_rub": 120_000,
            "max_days_past_due_12m": 0,
            "has_current_past_due": False,
            "credit_utilization": 0.35,
            "product_type": "term_loan",
            "purpose": "equipment",
            "company_segment": "small",
            "legal_form": "llc",
            "tax_regime": "usn",
            "client_rating": "A",
            "bki_credit_score": 820,
        }
    )
    bad = prod_scorer.score(
        {
            "company_age_months": 7,
            "employee_count": 1,
            "okved_risk": 0.6,
            "region_risk": 0.35,
            "annual_revenue_rub": 4_000_000,
            "monthly_revenue_rub": 330_000,
            "monthly_expenses_rub": 400_000,
            "total_debt_rub": 6_000_000,
            "requested_amount_rub": 5_000_000,
            "term_months": 24,
            "monthly_debt_payments_rub": 900_000,
            "max_days_past_due_12m": 45,
            "has_current_past_due": True,
            "credit_utilization": 0.95,
            "product_type": "term_loan",
            "purpose": "other",
            "company_segment": "micro",
            "legal_form": "llc",
            "tax_regime": "osn",
            "client_rating": "E",
            "bki_credit_score": 410,
        }
    )

    assert good.pd < bad.pd
    assert good.score > bad.score
    assert good.risk_grade in {"A", "B", "C", "D", "E"}
    assert good.reasons and bad.reasons
    # Политика должна отказать по стоп-фактору текущей просрочки
    assert bad.policy.decision == "decline"
    assert "CURRENT_PAST_DUE" in bad.policy.reasons

    # Защита от коллапса PD: на catboost-v3 хорошие и плохие заявки отличались
    # на 0.077 по PD и обе попадали в грейд E, поэтому формально тест
    # проходил, а модель в проде ничего не разделяла. Порог 0.12 выбран между
    # замеренными 0.077 (v3, коллапс) и 0.157 (v4, рабочая модель).
    assert bad.pd - good.pd > 0.12, f"PD spread too small: {bad.pd - good.pd:.4f}"
    assert good.risk_grade != "E", f"good applicant graded {good.risk_grade}"


def test_prod_artifact_serves_full_grpc_contract(prod_scorer):
    """Полный путь сервера: proto -> raw row -> score -> proto ответ."""
    submitted = Timestamp()
    submitted.FromDatetime(datetime(2026, 9, 1, tzinfo=timezone.utc))
    registered = Timestamp()
    registered.FromDatetime(datetime(2018, 4, 12, tzinfo=timezone.utc))

    request = scoring_pb2.ScoreApplicationRequest(
        application_id="prod-probe",
        application=scoring_pb2.Application(
            product_type=scoring_pb2.PRODUCT_TYPE_TERM_LOAN,
            requested_amount_rub=1_500_000,
            term_months=24,
            purpose=scoring_pb2.FINANCING_PURPOSE_EQUIPMENT,
            segment=scoring_pb2.BUSINESS_SEGMENT_SMALL,
            submitted_at=submitted,
        ),
        company=scoring_pb2.Company(
            inn="7701234567",
            legal_name="OOO Romashka",
            legal_form=scoring_pb2.LEGAL_FORM_LLC,
            okved="62.01",
            region="Moscow",
            registration_date=registered,
            employee_count=25,
        ),
        financials=scoring_pb2.Financials(
            annual_revenue_rub=120_000_000,
            monthly_revenue_rub=10_000_000,
            monthly_expenses_rub=8_000_000,
            total_debt_rub=3_000_000,
        ),
        credit_history=scoring_pb2.CreditHistory(
            active_obligations_count=2,
            total_outstanding_rub=3_000_000,
            monthly_debt_payments_rub=120_000,
            max_days_past_due_12m=0,
            has_current_past_due=False,
            credit_utilization=0.35,
            closed_obligations_count=4,
            applications_last_6m=1,
        ),
        extra_numeric_features={"bki_credit_score": 820.0, "tax_debt_rub": 0.0},
        extra_categorical_features={"client_rating": "A", "tax_regime": "usn"},
    )

    raw_row = request_to_raw_row(request)
    # Расширенные признаки из обогащения дошли до модели
    assert raw_row["bki_credit_score"] == 820.0
    assert raw_row["client_rating"] == "A"

    result = prod_scorer.score(raw_row)
    response = to_response(request.application_id, result)

    assert response.application_id == "prod-probe"
    assert response.model_version == CATBOOST_MODEL_VERSION
    assert 0 <= response.score <= 1000
    assert 0.0 <= response.pd <= 1.0
    assert response.risk_grade != scoring_pb2.RISK_GRADE_UNSPECIFIED
    assert response.decision.decision != scoring_pb2.DECISION_UNSPECIFIED
    assert len(response.reason_codes) > 0
    assert response.scored_at.ToSeconds() > 0
