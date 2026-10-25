from datetime import datetime, timezone

from ml_grpc.client import ScoringClient
from ml_grpc.exceptions import GrpcServiceError
from ml_grpc.mappers import proto_to_schema_response, schema_to_proto_score_request
from models.applications import ApplicationOrm
from models.auth import UserOrm
from repositories.applications import ApplicationRepository
from repositories.auth import UserRepository
from schemas.applications import (
    DEFAULT_PRODUCT_TYPE,
    SApplication,
    SApplicationCreateRequest,
    SScoreApplicationRequest,
)
from schemas.auth import _build_company, _build_credit_history, _build_financials
from services.enrichment import enrich, extract_ml_extra_features
from services.exceptions import ProfileIncompleteError
from services.scoring import decision_to_status
from services.ws_manager import ws_manager


class ApplicationService:
    """Оркестратор создания и обработки кредитной заявки"""

    @classmethod
    async def create_and_process(
        cls,
        user: UserOrm,
        create_request: SApplicationCreateRequest,
        client: ScoringClient,
    ) -> ApplicationOrm:
        """Создаёт заявку, обогащает, скорит, сохраняет результат и возвращает ORM"""
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

        application_schema = SApplication(
            product_type=create_request.product_type or DEFAULT_PRODUCT_TYPE,
            requested_amount_rub=create_request.requested_amount_rub,
            term_months=create_request.term_months,
            purpose=create_request.purpose,
            segment=create_request.segment,
            submitted_at=datetime.now(timezone.utc),
        )

        request_for_ml = SScoreApplicationRequest(
            application=application_schema,
            company=company,
            financials=financials,
            credit_history=credit_history,
        )

        application = await ApplicationRepository.create(
            user_id=refreshed.id,
            data=request_for_ml,
            product_type=create_request.product_type,
        )

        enriched = await enrich(company.inn)
        await ApplicationRepository.save_enriched(application.application_id, enriched)

        # Обогащение должно дойти до ML: без bki_credit_score модель подставляет
        # дефолт схемы и качество падает с AUC ~0.76 до ~0.55. Заявка в БД хранит
        # снапшот профиля (request_for_ml), а на скоринг уходит копия с признаками.
        extra_numeric, extra_categorical = extract_ml_extra_features(enriched)
        scoring_request = request_for_ml.model_copy(
            update={
                "extra_numeric_features": extra_numeric,
                "extra_categorical_features": extra_categorical,
            }
        )

        sources = [k for k, v in enriched.items() if v is not None]
        await ws_manager.broadcast(
            refreshed.id,
            {
                "type": "event",
                "application_id": application.application_id,
                "event_type": "enriched",
                "payload": {"sources": sources},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        try:
            proto_request = schema_to_proto_score_request(
                scoring_request, application.application_id
            )
            proto_response = await client.score_application(proto_request)
        except GrpcServiceError as exc:
            await ApplicationRepository.mark_failed(application.application_id, str(exc))
            await ws_manager.broadcast(
                refreshed.id,
                {
                    "type": "status_changed",
                    "application_id": application.application_id,
                    "status": "failed",
                    "payload": {"error": str(exc)},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            raise

        response = proto_to_schema_response(proto_response)
        decision_value = response.decision.decision if response.decision else None
        status = decision_to_status(decision_value, create_request.product_type)

        updated = await ApplicationRepository.update_scoring(
            application_id=application.application_id,
            scoring_result=response.model_dump(mode="json"),
            status=status,
        )

        await ws_manager.broadcast(
            refreshed.id,
            {
                "type": "status_changed",
                "application_id": application.application_id,
                "status": status,
                "payload": {
                    "score": response.score,
                    "risk_grade": response.risk_grade,
                    "decision": decision_value,
                    "reason_codes": [rc.model_dump() for rc in response.reason_codes],
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

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