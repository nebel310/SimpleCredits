import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from database import new_session
from models.applications import ApplicationOrm, ApplicationEventOrm
from schemas.applications import SScoreApplicationRequest


class ApplicationRepository:
    """Репозиторий для работы с кредитными заявками и их событиями"""

    @classmethod
    async def create(cls, user_id: int, data: SScoreApplicationRequest) -> ApplicationOrm:
        """Создаёт заявку со снимком профиля и пишет событие created"""
        application_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)

        async with new_session() as session:
            application = ApplicationOrm(
                application_id=application_id,
                user_id=user_id,
                status="pending",
                product_type=data.application.product_type,
                requested_amount_rub=data.application.requested_amount_rub,
                term_months=data.application.term_months,
                purpose=data.application.purpose,
                segment=data.application.segment,
                submitted_at=now,
                inn=data.company.inn,
                ogrn=data.company.ogrn,
                legal_name=data.company.legal_name,
                legal_form=data.company.legal_form,
                okved=data.company.okved,
                region=data.company.region,
                registration_date=data.company.registration_date,
                employee_count=data.company.employee_count,
                annual_revenue_rub=data.financials.annual_revenue_rub,
                annual_net_profit_rub=data.financials.annual_net_profit_rub,
                ebitda_rub=data.financials.ebitda_rub,
                total_debt_rub=data.financials.total_debt_rub,
                monthly_revenue_rub=data.financials.monthly_revenue_rub,
                monthly_expenses_rub=data.financials.monthly_expenses_rub,
                accounts_receivable_rub=data.financials.accounts_receivable_rub,
                cash_balance_rub=data.financials.cash_balance_rub,
                period_end=data.financials.period_end,
                active_obligations_count=data.credit_history.active_obligations_count,
                total_outstanding_rub=data.credit_history.total_outstanding_rub,
                monthly_debt_payments_rub=data.credit_history.monthly_debt_payments_rub,
                max_days_past_due_12m=data.credit_history.max_days_past_due_12m,
                has_current_past_due=data.credit_history.has_current_past_due,
                credit_utilization=data.credit_history.credit_utilization,
                closed_obligations_count=data.credit_history.closed_obligations_count,
                applications_last_6m=data.credit_history.applications_last_6m,
                created_at=now,
                updated_at=now,
            )
            session.add(application)
            await session.flush()
            session.add(
                ApplicationEventOrm(
                    application_id=application_id,
                    event_type="created",
                    payload={"user_id": user_id},
                    created_at=now,
                )
            )
            await session.commit()
            await session.refresh(application)
            return application

    @classmethod
    async def update_scoring(
        cls,
        application_id: str,
        scoring_result: dict,
        status: str,
        explanation: str | None = None,
        enriched_data: dict | None = None,
    ) -> ApplicationOrm | None:
        """Сохраняет результат скоринга, обогащение и статус, пишет события"""
        now = datetime.now(timezone.utc)

        async with new_session() as session:
            values: dict = {
                "scoring_result": scoring_result,
                "status": status,
                "updated_at": now,
            }
            if explanation is not None:
                values["explanation"] = explanation
            if enriched_data is not None:
                values["enriched_data"] = enriched_data

            await session.execute(
                update(ApplicationOrm)
                .where(ApplicationOrm.application_id == application_id)
                .values(**values)
            )
            session.add(
                ApplicationEventOrm(
                    application_id=application_id,
                    event_type="scored",
                    payload={
                        "score": scoring_result.get("score"),
                        "risk_grade": scoring_result.get("risk_grade"),
                    },
                    created_at=now,
                )
            )
            session.add(
                ApplicationEventOrm(
                    application_id=application_id,
                    event_type="status_changed",
                    payload={"status": status},
                    created_at=now,
                )
            )
            await session.commit()

        return await cls.get_by_application_id(application_id)

    @classmethod
    async def mark_failed(cls, application_id: str, reason: str | None = None) -> None:
        """Переводит заявку в статус failed и пишет событие failed"""
        now = datetime.now(timezone.utc)
        async with new_session() as session:
            await session.execute(
                update(ApplicationOrm)
                .where(ApplicationOrm.application_id == application_id)
                .values(status="failed", updated_at=now)
            )
            session.add(
                ApplicationEventOrm(
                    application_id=application_id,
                    event_type="failed",
                    payload={"reason": reason} if reason else {},
                    created_at=now,
                )
            )
            await session.commit()

    @classmethod
    async def add_event(
        cls,
        application_id: str,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        """Пишет событие по заявке"""
        async with new_session() as session:
            session.add(
                ApplicationEventOrm(
                    application_id=application_id,
                    event_type=event_type,
                    payload=payload or {},
                )
            )
            await session.commit()

    @classmethod
    async def get_by_application_id(cls, application_id: str) -> ApplicationOrm | None:
        """Возвращает заявку по публичному application_id"""
        async with new_session() as session:
            query = select(ApplicationOrm).where(
                ApplicationOrm.application_id == application_id
            )
            result = await session.execute(query)
            return result.scalars().first()

    @classmethod
    async def list_events(cls, application_id: str) -> list[ApplicationEventOrm]:
        """Возвращает события по заявке в хронологическом порядке"""
        async with new_session() as session:
            query = (
                select(ApplicationEventOrm)
                .where(ApplicationEventOrm.application_id == application_id)
                .order_by(ApplicationEventOrm.id.asc())
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    @classmethod
    async def get_user_applications_paginated(
        cls,
        user_id: int,
        cursor_id: int | None,
        direction: str,
        limit: int,
    ) -> tuple[list[ApplicationOrm], int | None, int | None]:
        """Возвращает список заявок пользователя с курсорной пагинацией"""
        async with new_session() as session:
            if direction == "forward":
                if cursor_id is not None:
                    query = (
                        select(ApplicationOrm)
                        .where(
                            ApplicationOrm.user_id == user_id,
                            ApplicationOrm.id > cursor_id,
                        )
                        .order_by(ApplicationOrm.id.asc())
                        .limit(limit + 1)
                    )
                else:
                    query = (
                        select(ApplicationOrm)
                        .where(ApplicationOrm.user_id == user_id)
                        .order_by(ApplicationOrm.id.asc())
                        .limit(limit + 1)
                    )
                result = await session.execute(query)
                items = result.scalars().all()
                rows = items[:limit]
                next_id = rows[-1].id if len(items) > limit else None
                prev_id = rows[0].id if cursor_id is not None else None

            elif direction == "backward":
                if cursor_id is not None:
                    query = (
                        select(ApplicationOrm)
                        .where(
                            ApplicationOrm.user_id == user_id,
                            ApplicationOrm.id < cursor_id,
                        )
                        .order_by(ApplicationOrm.id.desc())
                        .limit(limit + 1)
                    )
                else:
                    query = (
                        select(ApplicationOrm)
                        .where(ApplicationOrm.user_id == user_id)
                        .order_by(ApplicationOrm.id.desc())
                        .limit(limit + 1)
                    )
                result = await session.execute(query)
                items = result.scalars().all()
                items.reverse()
                rows = items[:limit]
                next_id = rows[-1].id if cursor_id is not None and len(items) > limit else None
                prev_id = rows[0].id if len(items) > limit else None

            else:
                raise ValueError("Invalid direction")

            return rows, next_id, prev_id