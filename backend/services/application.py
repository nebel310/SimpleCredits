import asyncio
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from ml_grpc.client import ScoringClient
from ml_grpc.exceptions import GrpcServiceError
from ml_grpc.mappers import proto_to_schema_response, schema_to_proto_score_request
from models.applications import ApplicationOrm
from models.auth import UserOrm
from repositories.applications import ApplicationRepository
from repositories.auth import UserRepository
from repositories.products import ProductRepository
from schemas.applications import (
    DEFAULT_PRODUCT_TYPE,
    SApplication,
    SApplicationCreateRequest,
    SCreditHistory,
    SDecisionResult,
    SScoreApplicationRequest,
    application_orm_to_schema,
)
from schemas.auth import _build_company, _build_credit_history, _build_financials
from services.enrichment import _credit_history_from_bki, enrich
from services.exceptions import ProductMismatchError, ProfileIncompleteError, RetryNotAllowedError
from services.products import (
    Applicant,
    build_offer,
    company_age_months,
    derive_segment,
    mismatch_reasons,
    no_product_explanation,
    pick_product,
    with_amount,
)
from services.deal import notify_status
from services.explain import FAILED_EXPLANATION, build_explanation
from services.scoring import decision_to_status
from services.ws_manager import ws_manager


NO_SUITABLE_PRODUCT = "NO_SUITABLE_PRODUCT"
# Проверка «есть ли заявка с этим ключом» и создание — атомарно в пределах процесса
_IDEMPOTENCY_LOCK = asyncio.Lock()
RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS = "RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS"


def decide_offer(application: ApplicationOrm, response, products) -> tuple[str | None, dict | None, str | None]:
    """
    Решение банка поверх ответа модели: тип результата, условия предложения и пояснение.

    Модель не знает каталога, поэтому:
    - если ни один продукт не подошёл — отказ NO_SUITABLE_PRODUCT;
    - если модель предлагает снизить сумму, а на неё выбранный продукт не выдаётся
      (меньше минимума) — подбираем другой продукт; не подошёл ни один — ручная проверка.
    Меняет response.decision на месте. Возвращает (outcome, offer, explanation).
    """
    applicant = _applicant_from_snapshot(application)
    chosen = next((p for p in products if p.product_type == application.product_type), None)
    if chosen is None:
        response.decision = SDecisionResult(decision="decline", reason_codes=[NO_SUITABLE_PRODUCT], conditions=[])
        return None, None, no_product_explanation(applicant)

    decision = response.decision
    if decision is None:
        return None, None, None
    grade = response.risk_grade

    if decision.decision == "approve":
        offer = build_offer(chosen, applicant.amount_rub, applicant.term_months, grade)
        outcome = "ALTERNATIVE_PRODUCT" if application.product_selected_by_system else None
        return outcome, offer, None

    if decision.decision == "approve_with_conditions":
        reduce = next((c for c in decision.conditions if c.code == "REDUCE_AMOUNT"), None)
        if reduce is None:
            return "COUNTER_OFFER", build_offer(chosen, applicant.amount_rub, applicant.term_months, grade), None
        reduced = with_amount(applicant, reduce.recommended_amount_rub)
        if not mismatch_reasons(chosen, reduced):
            return "COUNTER_OFFER", build_offer(chosen, reduced.amount_rub, reduced.term_months, grade), None
        alternative = pick_product(products, reduced)
        if alternative is not None:
            reduce.recommended_product_type = alternative.product_type
            return "ALTERNATIVE_PRODUCT", build_offer(alternative, reduced.amount_rub, reduced.term_months, grade), None
        response.decision = SDecisionResult(
            decision="manual_review",
            reason_codes=[*decision.reason_codes, RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS],
            conditions=[],
        )
        return "MANUAL_REVIEW", None, None

    if decision.decision == "manual_review":
        return "MANUAL_REVIEW", None, None

    return None, None, None


def add_bank_credits(history: SCreditHistory, offers: list[dict]) -> tuple[SCreditHistory, dict | None]:
    """
    Добавляет к кредитной истории кредиты, которые наш банк уже выдал клиенту.
    Мок БКИ о них не знает, а без них каждая новая заявка оценивалась бы как первая.
    Упрощение: считаем, что погашений по ним ещё не было — остаток равен сумме кредита.
    Возвращает историю и сводку для карточки (None — своих кредитов нет).
    """
    if not offers:
        return history, None
    count = len(offers)
    outstanding = sum(int(o.get("amount_rub") or 0) for o in offers)
    payments = sum(int(o.get("monthly_payment_rub") or 0) for o in offers)
    merged = history.model_copy(update={
        "active_obligations_count": history.active_obligations_count + count,
        "total_outstanding_rub": history.total_outstanding_rub + outstanding,
        "monthly_debt_payments_rub": history.monthly_debt_payments_rub + payments,
    })
    return merged, {"count": count, "outstanding_rub": outstanding, "monthly_payments_rub": payments}


def _applicant_from_snapshot(application: ApplicationOrm) -> Applicant:
    """Параметры заявки для правил каталога — из снимка, сохранённого при подаче"""
    return Applicant(
        segment=application.segment,
        purpose=application.purpose,
        amount_rub=application.requested_amount_rub,
        term_months=application.term_months,
        legal_form=application.legal_form,
        age_months=company_age_months(application.registration_date, application.submitted_at),
    )


class ApplicationService:
    """Оркестратор создания и обработки кредитной заявки"""

    @classmethod
    async def create_and_process(
        cls,
        user: UserOrm,
        create_request: SApplicationCreateRequest,
        client: ScoringClient,
        idempotency_key: str | None = None,
    ) -> ApplicationOrm:
        """
        Проверяет и создаёт заявку, затем обрабатывает её (обогащение, скоринг, решение).
        С тем же Idempotency-Key повторный запрос возвращает уже созданную заявку:
        проверка и создание идут под замком, поэтому двойной клик не создаст две заявки.
        """
        if idempotency_key:
            async with _IDEMPOTENCY_LOCK:
                existing = await ApplicationRepository.get_by_idempotency_key(user.id, idempotency_key)
                if existing is not None:
                    return existing
                application, created = await cls._create(user, create_request, idempotency_key)
        else:
            application, created = await cls._create(user, create_request, None)
        if not created:
            return application
        return await cls.process(application, client)

    @classmethod
    async def _create(
        cls,
        user: UserOrm,
        create_request: SApplicationCreateRequest,
        idempotency_key: str | None,
    ) -> tuple[ApplicationOrm, bool]:
        """Проверяет профиль и продукт, сохраняет заявку со снимком. Возвращает (заявка, создана ли новая)"""
        await cls._maybe_update_profile(user, create_request)

        refreshed = await UserRepository.get_user_by_id(user.id)
        if refreshed is None:
            raise ProfileIncompleteError("Пользователь не найден")

        company = _build_company(refreshed)
        financials = _build_financials(refreshed)
        credit_history = _build_credit_history(refreshed)

        if company is None or financials is None or credit_history is None:
            raise ProfileIncompleteError(
                "Профиль компании не заполнен. Заполните профиль через PATCH /auth/me "
                "или передайте данные company, financials, credit_history в теле заявки"
            )

        # Сегмент определяет банк по числу сотрудников и выручке, а не клиент
        segment = derive_segment(company.employee_count, financials.annual_revenue_rub)
        applicant = Applicant(
            segment=segment,
            purpose=create_request.purpose,
            amount_rub=create_request.requested_amount_rub,
            term_months=create_request.term_months,
            legal_form=company.legal_form,
            age_months=company_age_months(company.registration_date),
        )
        products = await ProductRepository.list_active()

        if create_request.product_type is not None:
            chosen = next((p for p in products if p.product_type == create_request.product_type), None)
            if chosen is None:
                raise ProductMismatchError(create_request.product_type, ["продукт недоступен"])
            reasons = mismatch_reasons(chosen, applicant)
            if reasons:
                raise ProductMismatchError(chosen.name, reasons)
            selected_by_system = False
        else:
            # Клиент не выбрал продукт — подбирает банк. Если не подошёл ни один,
            # заявка всё равно создаётся и получает отказ с причиной NO_SUITABLE_PRODUCT
            chosen = pick_product(products, applicant)
            selected_by_system = True

        application_schema = SApplication(
            product_type=chosen.product_type if chosen else DEFAULT_PRODUCT_TYPE,
            requested_amount_rub=create_request.requested_amount_rub,
            term_months=create_request.term_months,
            purpose=create_request.purpose,
            segment=segment,
            submitted_at=datetime.now(timezone.utc),
        )
        snapshot = SScoreApplicationRequest(
            application=application_schema,
            company=company,
            financials=financials,
            credit_history=credit_history,
        )
        try:
            application = await ApplicationRepository.create(
                user_id=refreshed.id,
                data=snapshot,
                product_type=chosen.product_type if chosen else None,
                product_selected_by_system=selected_by_system,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            # Запасной случай (несколько процессов бэкенда): второй запрос с тем же ключом
            # упирается в уникальный индекс — отдаём уже созданную заявку
            existing = await ApplicationRepository.get_by_idempotency_key(refreshed.id, idempotency_key or "")
            if existing is None:
                raise
            return existing, False
        return application, True

    @classmethod
    async def retry(cls, application: ApplicationOrm, client: ScoringClient) -> ApplicationOrm:
        """
        Повторяет проверку заявки после технической ошибки (failed): та же заявка,
        новая попытка обогащения и скоринга. Два повтора одновременно не запустятся:
        перевод failed → pending делается одним UPDATE.
        """
        if application.status != "failed":
            raise RetryNotAllowedError("Повторить можно только проверку, которая завершилась ошибкой")
        restarted = await ApplicationRepository.transition(
            application.application_id,
            from_statuses=("failed",),
            to_status="pending",
            event_type="retry_started",
        )
        if restarted is None:
            raise RetryNotAllowedError("Проверка уже запущена — обновите страницу")
        return await cls.process(restarted, client)

    @classmethod
    async def process(cls, application: ApplicationOrm, client: ScoringClient) -> ApplicationOrm:
        """
        Обрабатывает уже сохранённую заявку: ЕГРЮЛ/ФНС/БКИ, скоринг, решение.
        Всё берётся из снимка в заявке, поэтому обработку можно повторить.
        """
        enriched = await enrich(application.inn)
        await ApplicationRepository.save_enriched(application.application_id, enriched)

        # Кредитную историю действующего клиента банк берёт из БКИ (USERFLOW §6, п. 5).
        # Снимок заявки обновляется, чтобы модель, карточка и блок БКИ показывали одно и то же.
        # Если БКИ не ответил — берётся история из профиля.
        # К истории добавляются кредиты, которые наш банк уже выдал этому клиенту.
        bki_history = _credit_history_from_bki(enriched)
        own_offers = await ApplicationRepository.list_issued_offers(
            application.user_id, exclude_application_id=application.application_id
        )
        base_history = bki_history
        if base_history is None and own_offers:
            user = await UserRepository.get_user_by_id(application.user_id)
            base_history = (_build_credit_history(user) if user else None) or application_orm_to_schema(application).credit_history
        if base_history is not None:
            history, bank_credits = add_bank_credits(base_history, own_offers)
            if bank_credits:
                await ApplicationRepository.update_enriched(application.application_id, {**enriched, "bank_credits": bank_credits})
            application = await ApplicationRepository.save_credit_history(application.application_id, history) or application

        sources = [k for k, v in enriched.items() if v is not None]
        await ws_manager.broadcast(
            application.user_id,
            {
                "type": "event",
                "application_id": application.application_id,
                "event_type": "enriched",
                "payload": {"sources": sources},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        detail = application_orm_to_schema(application)
        request_for_ml = SScoreApplicationRequest(
            application=detail.application,
            company=detail.company,
            financials=detail.financials,
            credit_history=detail.credit_history,
        )

        try:
            proto_request = schema_to_proto_score_request(request_for_ml, application.application_id)
            proto_response = await client.score_application(proto_request)
        except GrpcServiceError as exc:
            # Заявка уже сохранена: номер нужен фронту, чтобы показать её, а не просить подать заново
            exc.application_id = application.application_id
            await ApplicationRepository.mark_failed(application.application_id, str(exc))
            application.status = "failed"
            await notify_status(application, explanation=FAILED_EXPLANATION)
            raise

        response = proto_to_schema_response(proto_response)
        products = await ProductRepository.list_active()
        outcome, offer, explanation = decide_offer(application, response, products)

        decision_value = response.decision.decision if response.decision else None
        client_chose_product = None if application.product_selected_by_system else application.product_type
        status = decision_to_status(decision_value, client_chose_product)
        if status != "different":
            outcome = None
        if explanation is None:
            explanation = build_explanation(
                status, outcome, response.decision.model_dump() if response.decision else None, offer,
                application.requested_amount_rub, bool(application.product_selected_by_system),
            )

        updated = await ApplicationRepository.update_scoring(
            application_id=application.application_id,
            scoring_result=response.model_dump(mode="json"),
            status=status,
            explanation=explanation,
            outcome=outcome,
            offer=offer,
        )

        await notify_status(updated or application)
        return updated or application

    @classmethod
    async def _maybe_update_profile(
        cls,
        user: UserOrm,
        create_request: SApplicationCreateRequest,
    ) -> None:
        """Обновляет профиль из тела заявки, если переданы блоки company/financials/credit_history"""
        update_data: dict = {}
        if create_request.company is not None:
            update_data["company"] = create_request.company.model_dump()
        if create_request.financials is not None:
            update_data["financials"] = create_request.financials.model_dump()
        if create_request.credit_history is not None:
            update_data["credit_history"] = create_request.credit_history.model_dump()

        if not update_data:
            return

        await UserRepository.update_user(user.id, update_data)
