from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent import futures
from datetime import datetime, timezone
from pathlib import Path

import grpc
from google.protobuf.timestamp_pb2 import Timestamp
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from simplecredits.ml.data.schema import CATEGORICAL_FEATURES, RAW_NUMERIC_FEATURES
from simplecredits.ml.scoring.model import CreditScorer, ScoreResult
from simplecredits.ml.training.catboost import (
    DEFAULT_CATBOOST_MODEL_PATH,
    train_catboost_model,
)
from simplecredits.ml.training.train import save_model
from simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc

PRODUCT_TYPES = {
    scoring_pb2.PRODUCT_TYPE_MICROLOAN: "microloan",
    scoring_pb2.PRODUCT_TYPE_TERM_LOAN: "term_loan",
    scoring_pb2.PRODUCT_TYPE_OVERDRAFT: "overdraft",
    scoring_pb2.PRODUCT_TYPE_CREDIT_LINE: "credit_line",
    scoring_pb2.PRODUCT_TYPE_LEASING: "leasing",
}

PURPOSES = {
    scoring_pb2.FINANCING_PURPOSE_WORKING_CAPITAL: "working_capital",
    scoring_pb2.FINANCING_PURPOSE_EQUIPMENT: "equipment",
    scoring_pb2.FINANCING_PURPOSE_EXPANSION: "expansion",
    scoring_pb2.FINANCING_PURPOSE_REFINANCING: "refinancing",
    scoring_pb2.FINANCING_PURPOSE_OTHER: "other",
}

RISK_GRADES = {
    "A": scoring_pb2.RISK_GRADE_A,
    "B": scoring_pb2.RISK_GRADE_B,
    "C": scoring_pb2.RISK_GRADE_C,
    "D": scoring_pb2.RISK_GRADE_D,
    "E": scoring_pb2.RISK_GRADE_E,
}

# Сегмент и организационно-правовая форма приходят в proto, но раньше не
# маппились в признаки — модель получала дефолты схемы вместо реальных
# значений. Словарь приведён к тому, что используется в обучающей таблице
# пайплайна: legal_form там хранится как ip / jsc / llc, а не как имена enum'ов.
COMPANY_SEGMENTS = {
    scoring_pb2.BUSINESS_SEGMENT_MICRO: "micro",
    scoring_pb2.BUSINESS_SEGMENT_SMALL: "small",
}

LEGAL_FORMS = {
    scoring_pb2.LEGAL_FORM_LLC: "llc",
    scoring_pb2.LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR: "ip",
    scoring_pb2.LEGAL_FORM_JOINT_STOCK_COMPANY: "jsc",
}

REASON_IMPACTS = {
    "positive": scoring_pb2.REASON_IMPACT_POSITIVE,
    "negative": scoring_pb2.REASON_IMPACT_NEGATIVE,
    "neutral": scoring_pb2.REASON_IMPACT_NEUTRAL,
}

DECISIONS = {
    "approve": scoring_pb2.DECISION_APPROVE,
    "approve_with_conditions": scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS,
    "manual_review": scoring_pb2.DECISION_MANUAL_REVIEW,
    "decline": scoring_pb2.DECISION_DECLINE,
}

OKVED_RISK_BY_PREFIX = {
    "01": 0.55,
    "02": 0.60,
    "10": 0.35,
    "41": 0.40,
    "43": 0.45,
    "45": 0.45,
    "46": 0.35,
    "47": 0.50,
    "49": 0.40,
    "55": 0.55,
    "56": 0.55,
    "61": 0.30,
    "62": 0.20,
    "63": 0.25,
    "68": 0.45,
    "69": 0.30,
    "71": 0.30,
    "73": 0.35,
    "74": 0.35,
    "86": 0.25,
}

REGION_RISK_BY_NAME = {
    "москва": 0.10,
    "санкт-петербург": 0.15,
    "московская область": 0.20,
    "республика татарстан": 0.25,
    "свердловская область": 0.30,
    "новосибирская область": 0.30,
    "краснодарский край": 0.32,
    "ростовская область": 0.35,
    "республика башкортостан": 0.32,
}


def estimate_okved_risk(okved: str) -> float:
    prefix = (okved or "").strip()[:2]
    return OKVED_RISK_BY_PREFIX.get(prefix, 0.40)


def estimate_region_risk(region: str) -> float:
    normalized = (region or "").strip().lower().replace("г.", "").strip()
    return REGION_RISK_BY_NAME.get(normalized, 0.40)


def request_to_raw_row(request: scoring_pb2.ScoreApplicationRequest) -> dict:
    application = request.application
    company = request.company
    financials = request.financials
    history = request.credit_history

    age_months = None
    if company.HasField("registration_date"):
        age_seconds = time.time() - company.registration_date.ToSeconds()
        age_months = max(0, int(age_seconds // (30 * 24 * 3600)))

    row = {
        "company_age_months": age_months,
        "employee_count": company.employee_count or None,
        "okved_risk": estimate_okved_risk(company.okved),
        "region_risk": estimate_region_risk(company.region),
        "annual_revenue_rub": financials.annual_revenue_rub or None,
        "annual_net_profit_rub": financials.annual_net_profit_rub,
        "ebitda_rub": financials.ebitda_rub,
        "total_debt_rub": financials.total_debt_rub,
        "monthly_revenue_rub": financials.monthly_revenue_rub or None,
        "monthly_expenses_rub": financials.monthly_expenses_rub or None,
        "accounts_receivable_rub": financials.accounts_receivable_rub,
        "cash_balance_rub": financials.cash_balance_rub,
        "requested_amount_rub": application.requested_amount_rub or None,
        "term_months": application.term_months or None,
        "active_obligations_count": history.active_obligations_count,
        "total_outstanding_rub": history.total_outstanding_rub,
        "monthly_debt_payments_rub": history.monthly_debt_payments_rub,
        "max_days_past_due_12m": history.max_days_past_due_12m,
        "has_current_past_due": history.has_current_past_due,
        "credit_utilization": history.credit_utilization,
        "closed_obligations_count": history.closed_obligations_count,
        "applications_last_6m": history.applications_last_6m,
        "product_type": PRODUCT_TYPES.get(application.product_type, "term_loan"),
        "purpose": PURPOSES.get(application.purpose, "other"),
        # proto несёт сегмент и правовую форму — отдаём их модели вместо
        # дефолтов схемы. extra_categorical_features ниже может их переопределить.
        "company_segment": COMPANY_SEGMENTS.get(application.segment, "micro"),
        "legal_form": LEGAL_FORMS.get(company.legal_form, "llc"),
    }

    unknown_numeric = sorted(
        set(request.extra_numeric_features) - set(RAW_NUMERIC_FEATURES)
    )
    if unknown_numeric:
        raise ValueError(f"unknown numeric features: {unknown_numeric}")
    unknown_categorical = sorted(
        set(request.extra_categorical_features) - set(CATEGORICAL_FEATURES)
    )
    if unknown_categorical:
        raise ValueError(f"unknown categorical features: {unknown_categorical}")
    row.update(request.extra_numeric_features)
    row.update(request.extra_categorical_features)
    return row


def to_response(application_id: str, result: ScoreResult) -> scoring_pb2.ScoreApplicationResponse:
    scored_at = Timestamp()
    scored_at.GetCurrentTime()
    reasons = [
        scoring_pb2.ReasonCode(
            code=reason["code"],
            description=reason["description"],
            feature=reason["feature"],
            impact=REASON_IMPACTS.get(reason["impact"], scoring_pb2.REASON_IMPACT_NEUTRAL),
            contribution=reason["contribution"],
        )
        for reason in result.reasons
    ]
    conditions = [
        scoring_pb2.DecisionCondition(
            code=condition.get("code", ""),
            description=condition.get("description", ""),
            recommended_amount_rub=int(condition.get("recommended_amount_rub", 0)),
        )
        for condition in result.policy.conditions
    ]
    decision = scoring_pb2.DecisionResult(
        decision=DECISIONS.get(result.policy.decision, scoring_pb2.DECISION_UNSPECIFIED),
        reason_codes=list(result.policy.reasons),
        conditions=conditions,
    )
    return scoring_pb2.ScoreApplicationResponse(
        application_id=application_id,
        score=result.score,
        pd=result.pd,
        risk_grade=RISK_GRADES.get(result.risk_grade, scoring_pb2.RISK_GRADE_E),
        reason_codes=reasons,
        model_version=result.model_version,
        scored_at=scored_at,
        decision=decision,
    )


class ScoringService(scoring_pb2_grpc.ScoringServiceServicer):
    def __init__(self, scorer: CreditScorer):
        self.scorer = scorer

    def ScoreApplication(self, request, context):
        try:
            raw_row = request_to_raw_row(request)
            result = self.scorer.score(raw_row)
        except Exception as error:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(error))
            raise
        return to_response(request.application_id, result)

    def BatchScoreApplications(self, request, context):
        results = []
        for application in request.applications:
            try:
                raw_row = request_to_raw_row(application)
                result = self.scorer.score(raw_row)
            except Exception as error:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(str(error))
                raise
            results.append(to_response(application.application_id, result))
        return scoring_pb2.BatchScoreApplicationsResponse(results=results)

    def GetModelInfo(self, request, context):
        info = self.scorer.model_info()
        response = scoring_pb2.GetModelInfoResponse(
            model_version=info["model_version"],
            model_type=info["model_type"],
            features=info["feature_columns"],
            metrics={key: float(value) for key, value in info["metrics"].items()},
        )
        trained_at = info.get("trained_at")
        if trained_at:
            parsed = datetime.fromisoformat(trained_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            response.trained_at.FromDatetime(parsed)
        return response


def ensure_model(model_path: Path) -> CreditScorer:
    """Загружает модель, при её отсутствии обучает запасную на синтетике.

    Запасная модель НЕ является прод-моделью: она обучена на синтетических
    данных, а не на таблице пайплайна, поэтому её метрики несравнимы с
    зафиксированными в артефакте. Случай используется для локальной разработки
    и тестов, а в прод-образе артефакт кладётся при сборке (ml/Dockerfile),
    поэтому до этой ветки дело доходить не должно.

    Обучаем именно CatBoost, чтобы тип модели совпадал с прод-моделью
    (catboost-v3): раньше здесь обучался линейный скоркард, и при пропаже
    артефакта сервер молча начинал отдавать другую модель того же «вида»
    на вид, но с другим поведением и без предупреждения.
    """
    if not model_path.exists():
        print(
            f"WARNING: model artifact not found at {model_path}; "
            "training a SYNTHETIC fallback model. This is NOT the production "
            "model and its metrics are not comparable to the committed artifact.",
            file=sys.stderr,
        )
        artifact = train_catboost_model(n_samples=20_000, seed=42)
        save_model(artifact, model_path)
    scorer = CreditScorer.load(model_path)
    print(
        f"serving model={scorer.model_version} type={scorer.model_type} "
        f"features={len(scorer.feature_columns or [])} "
        f"artifact={model_path}",
        file=sys.stderr,
    )
    return scorer


def create_server(scorer: CreditScorer, port: int, max_workers: int = 8) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(ScoringService(scorer), server)

    health_service = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_service, server)
    health_service.set("", health_pb2.HealthCheckResponse.SERVING)
    health_service.set(
        "simplecredits.scoring.v1.ScoringService",
        health_pb2.HealthCheckResponse.SERVING,
    )

    server.add_insecure_port(f"[::]:{port}")
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="SimpleCredits scoring gRPC server")
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL_PATH", str(DEFAULT_CATBOOST_MODEL_PATH)),
        help="path to the model artifact; defaults to MODEL_PATH env or the CatBoost model",
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("GRPC_PORT", "50051")))
    parser.add_argument("--workers", type=int, default=int(os.getenv("GRPC_WORKERS", "8")))
    args = parser.parse_args()

    scorer = ensure_model(Path(args.model))
    server = create_server(scorer, port=args.port, max_workers=args.workers)
    server.start()
    print(f"scoring gRPC server listening on :{args.port} (model={scorer.model_version})")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=2)


if __name__ == "__main__":
    main()
