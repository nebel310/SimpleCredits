"""Правила каталога: сегмент, возраст, подходит ли продукт, подбор, ставка и платёж"""
from datetime import datetime, timezone
from types import SimpleNamespace

from repositories.products import SEED_PRODUCTS
from services.products import (
    Applicant, annuity_payment, build_offer, company_age_months, derive_segment,
    mismatch_reasons, offer_rate, pick_product,
)

CATALOG = [SimpleNamespace(**p) for p in SEED_PRODUCTS]


def applicant(**kw):
    base = dict(segment="small", purpose="working_capital", amount_rub=1_000_000, term_months=12, legal_form="llc", age_months=60)
    base.update(kw)
    return Applicant(**base)


def by_type(t):
    return next(p for p in CATALOG if p.product_type == t)


def test_derive_segment_by_law_thresholds():
    assert derive_segment(15, 120_000_000) == "micro"
    assert derive_segment(16, 10_000_000) == "small"
    assert derive_segment(5, 120_000_001) == "small"


def test_company_age_months():
    now = datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert company_age_months(datetime(2026, 4, 25, tzinfo=timezone.utc), now) == 6
    assert company_age_months(datetime(2026, 4, 26, tzinfo=timezone.utc), now) == 5
    assert company_age_months(datetime(2018, 3, 15), now) == 103


def test_mismatch_reasons_lists_every_problem():
    reasons = mismatch_reasons(by_type("microloan"), applicant(segment="small", purpose="refinancing", amount_rub=40_000_000, term_months=120, legal_form="joint_stock_company", age_months=2))
    text = " | ".join(reasons)
    assert "микробизнес" in text and "цели" in text and "сумма" in text and "срок" in text
    assert "доступен только для" in text and "не меньше 6 мес." in text


def test_fitting_product_has_no_reasons():
    assert mismatch_reasons(by_type("term_loan"), applicant()) == []


def test_pick_product_cases_from_tz():
    """Строки таблицы из ТЗ (Бек-1): что должно подбираться"""
    # микробизнесу на оборудование 500 тыс подходят и микрозайм, и лизинг — лизинг дешевле
    assert pick_product(CATALOG, applicant(segment="micro", purpose="equipment", amount_rub=500_000, legal_form="individual_entrepreneur")).product_type == "leasing"
    # 300 тыс — меньше минимума лизинга, остаётся микрозайм
    assert pick_product(CATALOG, applicant(segment="micro", purpose="equipment", amount_rub=300_000, legal_form="individual_entrepreneur")).product_type == "microloan"
    assert pick_product(CATALOG, applicant(segment="micro", amount_rub=200_000, term_months=6, legal_form="individual_entrepreneur")).product_type == "term_loan"
    assert pick_product(CATALOG, applicant(purpose="equipment", amount_rub=35_000_000, term_months=60)).product_type == "leasing"
    assert pick_product(CATALOG, applicant(purpose="expansion", amount_rub=45_000_000, term_months=24)).product_type == "credit_line"
    assert pick_product(CATALOG, applicant(purpose="refinancing", amount_rub=5_000_000, term_months=24)).product_type == "term_loan"


def test_pick_product_none_when_nothing_fits():
    assert pick_product(CATALOG, applicant(amount_rub=90_000_000, term_months=24)) is None
    assert pick_product(CATALOG, applicant(age_months=2, segment="micro", legal_form="individual_entrepreneur")) is None


def test_pick_product_prefers_lowest_rate():
    """Оборотка 1 млн на 12 мес. для малого бизнеса: подходят оборотный, овердрафт, линия — берём самую дешёвую"""
    picked = pick_product(CATALOG, applicant())
    fitting = [p for p in CATALOG if not mismatch_reasons(p, applicant())]
    assert picked.rate_min_percent == min(p.rate_min_percent for p in fitting)


def test_offer_rate_by_grade():
    p = by_type("term_loan")  # 18–25%
    assert offer_rate(p, "A") == 18.0
    assert offer_rate(p, "C") == 21.5
    assert offer_rate(p, "E") == 25.0


def test_annuity_payment_known_value():
    assert annuity_payment(1_000_000, 12.0, 12) == 88_849
    assert annuity_payment(1_200_000, 0.0, 12) == 100_000


def test_build_offer_totals():
    offer = build_offer(by_type("term_loan"), 3_000_000, 12, "B")
    assert offer["product_type"] == "term_loan" and offer["rate_percent"] == 19.8
    assert offer["total_payment_rub"] == offer["monthly_payment_rub"] * 12
    assert offer["overpayment_rub"] == offer["total_payment_rub"] - 3_000_000
