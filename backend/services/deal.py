"""
Завершение сделки: клиент принимает предложение, подтверждает условия — кредит
оформляется и выдаётся. Выдача синтетическая: номер модельного договора и запись
в журнале, реальных проводок и документооборота нет.
"""
from datetime import datetime, timezone

from models.applications import ApplicationOrm
from repositories.applications import ApplicationRepository
from schemas.applications import ACCEPTABLE_OUTCOMES, available_actions, application_orm_to_schema, is_offer_outdated  # noqa: F401
from services.ws_manager import ws_manager

WHY_NOT = {
    "pending": "Заявка ещё обрабатывается",
    "failed": "Проверка не завершилась — сначала повторите её",
    "declined": "По заявке отказ — принимать нечего",
    "accepted": "Предложение уже принято",
    "issued": "Кредит уже оформлен",
    "rejected_by_client": "Вы отказались от этого предложения — подайте новую заявку",
}


OUTDATED_OFFER = (
    "После этого решения вам оформлен другой кредит — нагрузка изменилась, и условия больше не действуют. "
    "Подайте новую заявку: банк оценит её с учётом всех кредитов."
)


async def offer_outdated(application: ApplicationOrm) -> bool:
    """Предложение посчитано без кредита, который клиенту оформили позже"""
    counts = await ApplicationRepository.count_issued([application.inn])
    return is_offer_outdated(application, counts.get(application.inn, 0))


async def detail(application: ApplicationOrm):
    """Ответ API по заявке — с учётом кредитов, оформленных клиенту после её оценки"""
    counts = await ApplicationRepository.count_issued([application.inn])
    return application_orm_to_schema(application, counts.get(application.inn, 0))


async def details(applications: list[ApplicationOrm]) -> list:
    """То же для списка заявок: число оформленных кредитов считается одним запросом"""
    counts = await ApplicationRepository.count_issued([a.inn for a in applications])
    return [application_orm_to_schema(a, counts.get(a.inn, 0)) for a in applications]


class DealError(Exception):
    """Действие недоступно в текущем состоянии заявки (HTTP 409)"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _has_offer_to_accept(application: ApplicationOrm) -> bool:
    return "accept" in available_actions(application.status, application.outcome, bool(application.offer))


def _why_not(application: ApplicationOrm) -> str:
    if application.status == "different" and application.outcome == "MANUAL_REVIEW":
        return "Заявка на ручной проверке — дождитесь решения банка"
    return WHY_NOT.get(application.status, "Действие недоступно для этой заявки")


async def notify_status(application: ApplicationOrm, explanation: str | None = None) -> None:
    """
    WebSocket клиенту о смене статуса. Только то, что клиенту можно: статус, тип результата,
    объяснение и доступные действия. Балл, PD, грейд и факторы модели по WebSocket не уходят.
    """
    await ws_manager.broadcast(
        application.user_id,
        {
            "type": "status_changed",
            "application_id": application.application_id,
            "status": application.status,
            "payload": {
                "outcome": getattr(application, "outcome", None),
                "explanation": explanation if explanation is not None else getattr(application, "explanation", None),
                "actions": available_actions(
                    application.status, getattr(application, "outcome", None), bool(getattr(application, "offer", None))
                ),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


_notify = notify_status


async def accept_offer(application: ApplicationOrm) -> ApplicationOrm:
    """Клиент принимает предложение банка (одобрение, другой продукт или другие условия)"""
    if not _has_offer_to_accept(application):
        raise DealError(_why_not(application))
    if await offer_outdated(application):
        raise DealError(OUTDATED_OFFER)
    updated = await ApplicationRepository.transition(
        application.application_id,
        from_statuses=(application.status,),
        to_status="accepted",
        event_type="offer_accepted",
        payload={"offer": application.offer},
    )
    if updated is None:
        raise DealError("Статус заявки уже изменился — обновите страницу")
    await _notify(updated)
    return updated


async def issue_credit(application: ApplicationOrm) -> ApplicationOrm:
    """Клиент подтверждает условия — оформляем модельный договор и выдаём кредит"""
    if application.status != "accepted":
        raise DealError(
            "Сначала примите предложение" if _has_offer_to_accept(application) else _why_not(application)
        )
    if await offer_outdated(application):
        raise DealError(OUTDATED_OFFER)
    now = datetime.now(timezone.utc)
    contract_number = f"SC-{now:%Y%m%d}-{application.application_id[:6].upper()}"
    offer = application.offer or {}
    updated = await ApplicationRepository.transition(
        application.application_id,
        from_statuses=("accepted",),
        to_status="issued",
        event_type="issued",
        payload={
            "contract_number": contract_number,
            "amount_rub": offer.get("amount_rub"),
            "term_months": offer.get("term_months"),
            "rate_percent": offer.get("rate_percent"),
            "monthly_payment_rub": offer.get("monthly_payment_rub"),
        },
        values={"contract_number": contract_number, "issued_at": now},
    )
    if updated is None:
        raise DealError("Статус заявки уже изменился — обновите страницу")
    await _notify(updated)
    return updated


async def reject_offer(application: ApplicationOrm) -> ApplicationOrm:
    """Клиент отказывается от предложения (до оформления)"""
    if not (_has_offer_to_accept(application) or application.status == "accepted"):
        raise DealError(_why_not(application))
    updated = await ApplicationRepository.transition(
        application.application_id,
        from_statuses=(application.status,),
        to_status="rejected_by_client",
        event_type="offer_rejected",
    )
    if updated is None:
        raise DealError("Статус заявки уже изменился — обновите страницу")
    await _notify(updated)
    return updated
