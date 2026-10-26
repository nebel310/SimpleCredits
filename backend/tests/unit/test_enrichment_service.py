from services import enrichment as enrichment_module
from services.enrichment import enrich


async def test_enrich_returns_three_keys(monkeypatch):
    """enrich возвращает все три ключа"""

    async def fake_egrul(inn):
        return enrichment_module.generate_egrul(inn)

    async def fake_fns(inn):
        return enrichment_module.generate_fns(inn)

    async def fake_bki(inn):
        return enrichment_module.generate_bki(inn)

    monkeypatch.setattr(enrichment_module, "_call_egrul", fake_egrul)
    monkeypatch.setattr(enrichment_module, "_call_fns", fake_fns)
    monkeypatch.setattr(enrichment_module, "_call_bki", fake_bki)

    result = await enrich("7701234567")
    assert set(result.keys()) == {"egrul", "fns", "bki"}
    assert result["egrul"]["inn"] == "7701234567"
    assert result["fns"]["inn"] == "7701234567"
    assert result["bki"]["inn"] == "7701234567"


async def test_enrich_partial_failure_sets_none(monkeypatch):
    """Упавший генератор → None в соответствующем ключе"""

    async def ok_egrul(inn):
        return enrichment_module.generate_egrul(inn)

    async def fail_fns(inn):
        raise RuntimeError("fns down")

    async def ok_bki(inn):
        return enrichment_module.generate_bki(inn)

    monkeypatch.setattr(enrichment_module, "_call_egrul", ok_egrul)
    monkeypatch.setattr(enrichment_module, "_call_fns", fail_fns)
    monkeypatch.setattr(enrichment_module, "_call_bki", ok_bki)

    result = await enrich("7701234567")
    assert result["egrul"] is not None
    assert result["fns"] is None
    assert result["bki"] is not None


async def test_enrich_all_failed(monkeypatch):
    """Все три упали → все None"""

    async def fail(inn):
        raise RuntimeError("down")

    monkeypatch.setattr(enrichment_module, "_call_egrul", fail)
    monkeypatch.setattr(enrichment_module, "_call_fns", fail)
    monkeypatch.setattr(enrichment_module, "_call_bki", fail)

    result = await enrich("7701234567")
    assert result == {"egrul": None, "fns": None, "bki": None}


async def test_enrich_serializes_to_dict(monkeypatch):
    """Результат сериализуется в JSON-совместимый dict"""

    async def fake_egrul(inn):
        return enrichment_module.generate_egrul(inn)

    async def fake_fns(inn):
        return enrichment_module.generate_fns(inn)

    async def fake_bki(inn):
        return enrichment_module.generate_bki(inn)

    monkeypatch.setattr(enrichment_module, "_call_egrul", fake_egrul)
    monkeypatch.setattr(enrichment_module, "_call_fns", fake_fns)
    monkeypatch.setattr(enrichment_module, "_call_bki", fake_bki)

    result = await enrich("7701234567")
    import json
    json.dumps(result)  # не должно кидать

def test_extract_ml_extra_features_maps_bki_and_fns():
    """credit_score, tax_debt_rub и tax_regime доходят до extra_*_features"""
    from services.enrichment import extract_ml_extra_features

    enriched = {
        "egrul": {"inn": "7701234567"},
        "fns": {"tax_regime": "УСН", "tax_debt_rub": 15000},
        "bki": {"credit_score": 742},
    }

    numeric, categorical = extract_ml_extra_features(enriched)

    assert numeric["bki_credit_score"] == 742.0
    assert numeric["tax_debt_rub"] == 15000.0
    assert categorical["tax_regime"] == "usn"


def test_extract_ml_extra_features_normalizes_all_tax_regimes():
    """Кириллические режимы ФНС приводятся к слагам ML"""
    from services.enrichment import TAX_REGIME_TO_ML, extract_ml_extra_features

    for raw, slug in TAX_REGIME_TO_ML.items():
        _, categorical = extract_ml_extra_features({"fns": {"tax_regime": raw}})
        assert categorical["tax_regime"] == slug


def test_extract_ml_extra_features_tolerates_missing_sources():
    """Упавший источник (None) не ломает извлечение"""
    from services.enrichment import extract_ml_extra_features

    numeric, categorical = extract_ml_extra_features(
        {"egrul": None, "fns": None, "bki": None}
    )

    assert numeric == {}
    assert categorical == {}


def test_extract_ml_extra_features_skips_unsafe_fields():
    """Поля вне распределения обучения намеренно не отдаются"""
    from services.enrichment import extract_ml_extra_features

    enriched = {
        "fns": {
            "mass_address": True,
            "mass_director": True,
            "disqualified_persons": True,
            "reliability_score": 95,
            "tax_debt_rub": 0,
        },
        "bki": {"credit_score": 800},
    }

    numeric, categorical = extract_ml_extra_features(enriched)

    # mass_* константны в обучении, reliability_score — другая шкала
    assert "mass_address_flag" not in numeric
    assert "mass_manager_flag" not in numeric
    assert "disqualified_manager_flag" not in numeric
    assert "reputation_rating" not in numeric
    assert set(numeric) == {"bki_credit_score", "tax_debt_rub"}
