"""Решение сотрудника банка по заявке, которую модель отправила на ручную проверку"""
from datetime import datetime, timezone

from models.applications import ApplicationOrm
from repositories.applications import ApplicationRepository
from repositories.products import ProductRepository
from schemas.applications import SBankDecisionRequest
from services.deal import DealError, notify_status
from services.products import build_offer, mismatch_reasons, pick_product, with_amount


async def decide_manual_review(application: ApplicationOrm, body: SBankDecisionRequest, decided_by: str) -> ApplicationOrm:
    """
    Закрывает ручную проверку решением банка:
    approve — одобрить на запрошенных условиях;
    approve_with_conditions — предложить другую сумму (при необходимости — другой продукт);
    decline — отказать.
    Решение модели в scoring_result не меняется — видно, что решил человек и почему.
    """
    if not (application.status == "different" and application.outcome == "MANUAL_REVIEW"):
        raise DealError("Решение принимается только по заявкам на ручной проверке")

    from services.application import _applicant_from_snapshot  # локальный импорт: избегаем цикла

    applicant = _applicant_from_snapshot(application)
    products = await ProductRepository.list_active()
    chosen = next((p for p in products if p.product_type == application.product_type), None)
    grade = (application.scoring_result or {}).get("risk_grade", "E")

    record = {
        "decision": body.decision,
        "comment": body.comment,
        "recommended_amount_rub": body.recommended_amount_rub,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": decided_by,
    }
    values = {"bank_decision": record, "explanation": body.comment}

    if body.decision == "decline":
        to_status, values["outcome"], values["offer"] = "declined", None, None
    elif chosen is None:
        raise DealError("У заявки нет подходящего продукта — одобрить можно только с другой суммой")
    elif body.decision == "approve":
        values["offer"] = build_offer(chosen, applicant.amount_rub, applicant.term_months, grade)
        if application.product_selected_by_system:
            to_status, values["outcome"] = "different", "ALTERNATIVE_PRODUCT"
        else:
            to_status, values["outcome"] = "confirmed", None
    else:
        if body.recommended_amount_rub >= applicant.amount_rub:
            raise DealError("Одобрить с другой суммой можно только на меньшую сумму, чем запросил клиент")
        reduced = with_amount(applicant, body.recommended_amount_rub)
        product = chosen if not mismatch_reasons(chosen, reduced) else pick_product(products, reduced)
        if product is None:
            raise DealError("На эту сумму нет подходящего продукта — укажите другую сумму")
        values["offer"] = build_offer(product, reduced.amount_rub, reduced.term_months, grade)
        to_status = "different"
        values["outcome"] = "COUNTER_OFFER" if product is chosen else "ALTERNATIVE_PRODUCT"

    updated = await ApplicationRepository.transition(
        application.application_id,
        from_statuses=("different",),
        to_status=to_status,
        event_type="bank_decision",
        payload={"decision": body.decision, "comment": body.comment, "outcome": values.get("outcome")},
        values=values,
    )
    if updated is None:
        raise DealError("Статус заявки уже изменился — обновите страницу")
    await notify_status(updated)
    return updated
