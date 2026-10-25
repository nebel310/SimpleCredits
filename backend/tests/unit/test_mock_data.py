from datetime import datetime, timezone

from services.mock_data import (
    generate_bki,
    generate_egrul,
    generate_fns,
    is_valid_inn,
)


FIXED_NOW = datetime(2026, 3, 15, tzinfo=timezone.utc)


def test_is_valid_inn_10_digits():
    """10-значный ИНН валиден"""
    assert is_valid_inn("7701234567") is True


def test_is_valid_inn_12_digits():
    """12-значный ИНН валиден"""
    assert is_valid_inn("770123456789") is True


def test_is_valid_inn_short():
    """ИНН короче 10 символов невалиден"""
    assert is_valid_inn("123") is False


def test_is_valid_inn_long():
    """ИНН длиннее 12 символов невалиден"""
    assert is_valid_inn("1" * 13) is False


def test_is_valid_inn_not_digits():
    """ИНН с буквами невалиден"""
    assert is_valid_inn("77012345ab") is False


def test_is_valid_inn_empty():
    """Пустой ИНН невалиден"""
    assert is_valid_inn("") is False


def test_egrul_deterministic():
    """Два вызова generate_egrul с одним ИНН дают одинаковые данные"""
    a = generate_egrul("7701234567", now=FIXED_NOW)
    b = generate_egrul("7701234567", now=FIXED_NOW)
    assert a.model_dump() == b.model_dump()


def test_egrul_different_inns():
    """Разные ИНН дают разные данные"""
    a = generate_egrul("7701234567", now=FIXED_NOW)
    b = generate_egrul("7707654321", now=FIXED_NOW)
    assert a.model_dump() != b.model_dump()


def test_egrul_fields():
    """Все поля ЕГРЮЛ заполнены корректно"""
    e = generate_egrul("7701234567", now=FIXED_NOW)
    assert e.inn == "7701234567"
    assert len(e.ogrn) == 13
    assert e.ogrn.isdigit()
    assert e.legal_form in ("llc", "joint_stock_company")
    assert e.employee_count >= 1
    assert e.status == "active"


def test_fns_deterministic():
    """ФНС детерминирован"""
    assert (
        generate_fns("7701234567", now=FIXED_NOW).model_dump()
        == generate_fns("7701234567", now=FIXED_NOW).model_dump()
    )


def test_fns_reliability_range():
    """reliability_score в [40, 100]"""
    f = generate_fns("7701234567", now=FIXED_NOW)
    assert 40 <= f.reliability_score <= 100


def test_fns_mass_flags_boolean():
    """Флаги mass_address/mass_director — bool"""
    f = generate_fns("7701234567", now=FIXED_NOW)
    assert isinstance(f.mass_address, bool)
    assert isinstance(f.mass_director, bool)


def test_fns_debt_non_negative():
    """Налоговый долг неотрицателен"""
    f = generate_fns("7701234567", now=FIXED_NOW)
    assert f.tax_debt_rub >= 0


def test_bki_deterministic():
    """БКИ детерминирован"""
    assert (
        generate_bki("7701234567", now=FIXED_NOW).model_dump()
        == generate_bki("7701234567", now=FIXED_NOW).model_dump()
    )


def test_bki_credit_score_range():
    """credit_score в [300, 850]"""
    b = generate_bki("7701234567", now=FIXED_NOW)
    assert 300 <= b.credit_score <= 850


def test_bki_credit_utilization_range():
    """credit_utilization в [0, 1]"""
    b = generate_bki("7701234567", now=FIXED_NOW)
    assert 0.0 <= b.credit_utilization <= 1.0


def test_bki_max_days_non_negative():
    """max_days_past_due_12m неотрицателен"""
    b = generate_bki("7701234567", now=FIXED_NOW)
    assert b.max_days_past_due_12m >= 0


def test_bki_has_current_past_due_bool():
    """has_current_past_due — bool"""
    b = generate_bki("7701234567", now=FIXED_NOW)
    assert isinstance(b.has_current_past_due, bool)


def test_bki_no_active_no_payments():
    """При active=0 ежемесячный платёж = 0"""
    b = generate_bki("7701234567", now=FIXED_NOW)
    if b.active_obligations_count == 0:
        assert b.monthly_debt_payments_rub == 0


def test_egrul_form_matches_inn_length():
    """12 цифр ИНН — ИП с ОГРНИП из 15 цифр, 10 цифр — ООО/АО с ОГРН из 13 цифр"""
    for inn in ("500100732259", "771234567890", "502345678901"):
        e = generate_egrul(inn)
        assert e.legal_form == "individual_entrepreneur" and len(e.ogrn) == 15 and e.ogrn[0] == "3"
        assert e.legal_name.startswith("ИП ") and e.employee_count <= 15
    for inn in ("7707083893", "7712345678", "7723456789"):
        e = generate_egrul(inn)
        assert e.legal_form in ("llc", "joint_stock_company") and len(e.ogrn) == 13 and e.ogrn[0] == "1"


def test_fns_patent_only_for_ip():
    for i in range(300):
        inn10, inn12 = f"77{i:08d}", f"77{i:010d}"
        assert generate_fns(inn10).tax_regime in ("УСН", "ОСН")
        assert generate_fns(inn12).tax_regime in ("УСН", "ПАТЕНТ", "ОСН")


def test_bki_internally_consistent():
    """Нет кредитов — нет долга, платежей и загрузки; платёж соразмерен остатку; текущая просрочка видна в истории"""
    for i in range(500):
        b = generate_bki(f"77{i:08d}")
        if b.active_obligations_count == 0:
            assert b.total_outstanding_rub == 0 and b.monthly_debt_payments_rub == 0 and b.credit_utilization == 0
            assert not b.has_current_past_due
        else:
            assert 0.03 * b.total_outstanding_rub - 1 <= b.monthly_debt_payments_rub <= 0.08 * b.total_outstanding_rub + 1
        if b.has_current_past_due:
            assert b.max_days_past_due_12m >= 1
