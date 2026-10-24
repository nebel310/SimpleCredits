from services.enrichment import enrich


async def test_enrich_real_generators():
    """enrich с реальными генераторами возвращает все три ключа"""
    result = await enrich("7701234567")
    assert result["egrul"] is not None
    assert result["fns"] is not None
    assert result["bki"] is not None
    assert result["egrul"]["inn"] == "7701234567"


async def test_enrich_deterministic_numeric_fields():
    """Числовые поля стабильны между вызовами"""
    a = await enrich("7701234567")
    b = await enrich("7701234567")
    assert a["egrul"]["employee_count"] == b["egrul"]["employee_count"]
    assert a["bki"]["credit_score"] == b["bki"]["credit_score"]
    assert a["fns"]["reliability_score"] == b["fns"]["reliability_score"]


async def test_enrich_two_different_inns_differ():
    """Разные ИНН дают разные числовые поля"""
    a = await enrich("7701234567")
    b = await enrich("7707654321")
    assert a["bki"]["credit_score"] != b["bki"]["credit_score"] or \
           a["egrul"]["employee_count"] != b["egrul"]["employee_count"]