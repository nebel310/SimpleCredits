"""
Короткое объяснение решения для клиента (поле explanation) — по шаблонам из кодов причин.
Технические коды остаются внутри системы, наружу — понятный текст.
"""

POLICY_REASON_TEXT = {
    "CURRENT_PAST_DUE": "сейчас есть просрочка по кредитам",
    "SEVERE_PAST_DUE_HISTORY": "за последний год была просрочка 60 дней и больше",
    "HIGH_RISK_SCORE": "высокий риск по оценке модели",
    "RISK_IN_GREY_ZONE": "оценка риска в пограничной зоне",
    "HIGH_DEBT_SERVICE_RATIO": "платежи по долгам больше 55% месячной выручки",
    "LOAN_TO_REVENUE_REDUCTION": "запрошенная сумма больше 60% годовой выручки",
    "RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS": "на рекомендованную сумму нет подходящего продукта",
}


def _money(value: int | None) -> str:
    return f"{value or 0:,}".replace(",", " ") + " ₽"


def _reasons(codes: list[str]) -> str:
    texts = [POLICY_REASON_TEXT[c] for c in codes if c in POLICY_REASON_TEXT]
    return "; ".join(texts)


def build_explanation(status: str, outcome: str | None, decision: dict | None, offer: dict | None,
                      requested_amount_rub: int, selected_by_system: bool) -> str | None:
    """Текст для клиента по итогу автоматической обработки. None — объяснять нечего"""
    codes = (decision or {}).get("reason_codes") or []
    why = _reasons(codes)
    if offer:
        terms = (f"«{offer['product_name']}», {_money(offer['amount_rub'])} на {offer['term_months']} мес. "
                 f"под {offer['rate_percent']}% годовых, платёж {_money(offer['monthly_payment_rub'])} в месяц")
    else:
        terms = ""
    if status == "confirmed" and offer:
        return f"Одобрено на запрошенных условиях: {terms}."
    if outcome == "ALTERNATIVE_PRODUCT" and offer:
        if selected_by_system and offer["amount_rub"] == requested_amount_rub:
            return f"Подобрали продукт под вашу заявку: {terms}."
        return f"Предлагаем другой продукт: {terms}." + (f" Причина: {why}." if why else "")
    if outcome == "COUNTER_OFFER" and offer:
        return (f"Можем одобрить {_money(offer['amount_rub'])} вместо {_money(requested_amount_rub)}: {terms}."
                + (f" Причина: {why}." if why else ""))
    if outcome == "MANUAL_REVIEW":
        return ("Нужна дополнительная проверка сотрудником банка" + (f": {why}" if why else "")
                + ". Решение появится в этой заявке.")
    if status == "declined":
        return "Банк отказал" + (f": {why}" if why else "") + "."
    return None


FAILED_EXPLANATION = "Проверка не завершилась из-за технического сбоя. Данные заявки сохранены — повторите проверку."
