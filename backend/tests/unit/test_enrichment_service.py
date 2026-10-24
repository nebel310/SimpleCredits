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