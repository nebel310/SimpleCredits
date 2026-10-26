"""Прод-доступность признаков: пул, из которого идёт отбор при обучении.

Модель должна опираться только на то, что backend реально передаёт. Эти тесты
фиксируют сам механизм определения доступности и его согласованность с
serving-слоем.
"""

from simplecredits.ml.data.schema import CATEGORICAL_FEATURES, DEFAULT_RAW_ROW
from simplecredits.ml.features.availability import (
    SERVING_AVAILABLE_COLUMNS,
    SERVING_ENRICHED_COLUMNS,
    SERVING_PROTO_COLUMNS,
    serving_available_features,
    unavailable_features,
)
from simplecredits.ml.features.features import FEATURE_COLUMNS


def test_available_and_unavailable_partition_feature_columns():
    """Два множества дают точное разбиение FEATURE_COLUMNS."""
    available = serving_available_features()
    unavailable = unavailable_features()

    assert set(available) | set(unavailable) == set(FEATURE_COLUMNS)
    assert set(available) & set(unavailable) == set()
    assert len(available) + len(unavailable) == len(FEATURE_COLUMNS)
    # Порядок следует FEATURE_COLUMNS
    assert available == [c for c in FEATURE_COLUMNS if c in set(available)]


def test_available_features_is_deterministic():
    """Результат не зависит от запуска: иначе обучение невоспроизводимо."""
    assert serving_available_features() == serving_available_features()


def test_serving_columns_are_subset_of_schema():
    """Колонки сервера существуют в схеме, иначе возмущения теряются молча."""
    unknown = SERVING_AVAILABLE_COLUMNS - set(DEFAULT_RAW_ROW)
    assert unknown == set(), f"columns absent from DEFAULT_RAW_ROW: {sorted(unknown)}"


def test_proto_columns_match_request_to_raw_row():
    """SERVING_PROTO_COLUMNS совпадает с тем, что заполняет request_to_raw_row.

    Проверка на поведении, а не на тексте исходника: вызываем серверную функцию
    с заполненным proto-запросом и сверяем реально созданные ключи. Если в
    serving добавят или уберут поле, тест укажет на рассинхрон со списком
    доступности — иначе модель будет считать признак «доступным», которого
    сервер уже не отдаёт.
    """
    from google.protobuf.timestamp_pb2 import Timestamp

    from simplecredits.ml.serving.server import request_to_raw_row
    from simplecredits.scoring.v1 import scoring_pb2

    stamp = Timestamp()
    stamp.GetCurrentTime()

    request = scoring_pb2.ScoreApplicationRequest(
        application_id="availability-probe",
        application=scoring_pb2.Application(
            product_type=scoring_pb2.PRODUCT_TYPE_TERM_LOAN,
            requested_amount_rub=1_000_000,
            term_months=12,
            purpose=scoring_pb2.FINANCING_PURPOSE_EQUIPMENT,
            segment=scoring_pb2.BUSINESS_SEGMENT_SMALL,
            submitted_at=stamp,
        ),
        company=scoring_pb2.Company(
            inn="7701234567",
            legal_name="Probe",
            legal_form=scoring_pb2.LEGAL_FORM_LLC,
            okved="62.01",
            region="Moscow",
            registration_date=stamp,
            employee_count=10,
        ),
        financials=scoring_pb2.Financials(
            annual_revenue_rub=10_000_000,
            monthly_revenue_rub=900_000,
            monthly_expenses_rub=700_000,
            total_debt_rub=1_000_000,
        ),
        credit_history=scoring_pb2.CreditHistory(
            active_obligations_count=1,
            total_outstanding_rub=1_000_000,
            monthly_debt_payments_rub=50_000,
            credit_utilization=0.3,
            closed_obligations_count=2,
            applications_last_6m=1,
        ),
    )

    produced = set(request_to_raw_row(request))

    missing_in_list = produced - SERVING_PROTO_COLUMNS
    assert missing_in_list == set(), (
        "request_to_raw_row emits columns absent from SERVING_PROTO_COLUMNS "
        f"(add them, or the model will treat them as unavailable): {sorted(missing_in_list)}"
    )

    stale = SERVING_PROTO_COLUMNS - produced
    assert stale == set(), (
        "SERVING_PROTO_COLUMNS lists columns the server no longer produces "
        f"(model would trust defaults that never arrive): {sorted(stale)}"
    )


def test_enriched_columns_cover_backend_extractor():
    """Колонки обогащения совпадают с тем, что отдаёт backend.

    Backend: services/enrichment.py::extract_ml_extra_features маппит
    bki.credit_score, fns.tax_debt_rub и fns.tax_regime.
    """
    assert SERVING_ENRICHED_COLUMNS == {"bki_credit_score", "tax_debt_rub", "tax_regime"}


def test_derived_features_follow_their_sources():
    """Производный признак доступен, если доступны его исходные колонки."""
    available = set(serving_available_features())

    # Все эти признаки строятся из колонок, которые backend передаёт.
    for feature in ("debt_to_revenue", "debt_service_ratio", "log_annual_revenue"):
        assert feature in available

    # Признаки из недоступных сырых колонок должны остаться недоступными.
    for feature in ("txn_inflow_90d", "court_cases_count", "fraud_flag"):
        assert feature not in available
        assert feature in set(unavailable_features())


def test_categorical_availability_follows_backend_mapping():
    """Доступны только те категориальные признаки, что backend реально отдаёт."""
    available = set(serving_available_features())

    # segment и legal_form замапплены в request_to_raw_row, tax_regime — из ФНС.
    for feature in ("company_segment", "legal_form", "tax_regime"):
        assert feature in available, feature

    # product_type и purpose приходят из proto.
    assert "product_type" in available
    assert "purpose" in available

    # client_rating backend не передаёт: он строится пайплайном из
    # bank_internal_history, а не из заявки.
    assert "client_rating" not in available
    assert "client_rating" in CATEGORICAL_FEATURES


def test_pool_is_much_smaller_than_full_feature_set():
    """Смысл ограничения виден: прод-пул заметно меньше полного набора.

    Если пул однажды сравняется с FEATURE_COLUMNS, ограничение перестало
    что-либо значить и тест стоит пересмотреть осознанно.
    """
    available = serving_available_features()

    assert len(available) < len(FEATURE_COLUMNS) / 2
    assert len(available) >= 20, f"pool too small to be useful: {len(available)}"
