def decision_to_status(decision: str | None, product_type: str | None) -> str:
    """
    Маппит decision ML-сервиса в финальный статус заявки.

    approve + product_type указан → confirmed
    approve + product_type=None → different
    approve_with_conditions / manual_review → different
    decline → declined
    decision=None / неизвестное → failed
    """
    if decision is None:
        return "failed"
    if decision == "approve":
        return "confirmed" if product_type else "different"
    if decision in ("approve_with_conditions", "manual_review"):
        return "different"
    if decision == "decline":
        return "declined"
    return "failed"