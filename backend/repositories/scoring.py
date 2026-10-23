import uuid

from sqlalchemy import select, update

from database import new_session
from models.scoring import ApplicationOrm, ScoringResultOrm
from schemas.scoring import SScoreApplicationRequest


class ScoringRepository:
    """Репозиторий для работы с кредитными заявками и результатами скоринга"""

    @classmethod
    async def create_application(cls, user_id: int, data: SScoreApplicationRequest) -> ApplicationOrm:
        """Создаёт заявку с новым application_id и возвращает её"""
        application_id = uuid.uuid4().hex

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
                submitted_at=data.application.submitted_at,
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
            )

            session.add(application)
            await session.commit()
            await session.refresh(application)
            return application

    @classmethod
    async def save_scoring_result(cls, application_id: str, result: dict) -> ScoringResultOrm:
        """Сохраняет результат скоринга и переводит заявку в статус scored"""
        async with new_session() as session:
            scoring_result = ScoringResultOrm(
                application_id=application_id,
                score=result["score"],
                pd=result["pd"],
                risk_grade=result["risk_grade"],
                model_version=result["model_version"],
                scored_at=result["scored_at"],
                decision=result["decision"],
                reason_codes=result["reason_codes"],
                conditions=result["conditions"],
            )
            session.add(scoring_result)

            await session.execute(
                update(ApplicationOrm)
                .where(ApplicationOrm.application_id == application_id)
                .values(status="scored")
            )

            await session.commit()
            await session.refresh(scoring_result)
            return scoring_result

    @classmethod
    async def mark_application_failed(cls, application_id: str) -> None:
        """Переводит заявку в статус failed"""
        async with new_session() as session:
            await session.execute(
                update(ApplicationOrm)
                .where(ApplicationOrm.application_id == application_id)
                .values(status="failed")
            )
            await session.commit()

    @classmethod
    async def get_application_by_application_id(cls, application_id: str) -> ApplicationOrm | None:
        """Возвращает заявку по её публичному application_id"""
        async with new_session() as session:
            query = select(ApplicationOrm).where(
                ApplicationOrm.application_id == application_id
            )
            result = await session.execute(query)
            return result.scalars().first()

    @classmethod
    async def get_scoring_result_by_application_id(cls, application_id: str) -> ScoringResultOrm | None:
        """Возвращает результат скоринга по application_id"""
        async with new_session() as session:
            query = select(ScoringResultOrm).where(
                ScoringResultOrm.application_id == application_id
            )
            result = await session.execute(query)
            return result.scalars().first()

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
                    query = select(ApplicationOrm).where(
                        ApplicationOrm.user_id == user_id,
                        ApplicationOrm.id > cursor_id,
                    ).order_by(ApplicationOrm.id.asc()).limit(limit + 1)
                else:
                    query = select(ApplicationOrm).where(
                        ApplicationOrm.user_id == user_id,
                    ).order_by(ApplicationOrm.id.asc()).limit(limit + 1)

                result = await session.execute(query)
                items = result.scalars().all()
                rows = items[:limit]
                next_id = rows[-1].id if len(items) > limit else None
                prev_id = rows[0].id if cursor_id is not None else None

            elif direction == "backward":
                if cursor_id is not None:
                    query = select(ApplicationOrm).where(
                        ApplicationOrm.user_id == user_id,
                        ApplicationOrm.id < cursor_id,
                    ).order_by(ApplicationOrm.id.desc()).limit(limit + 1)
                else:
                    query = select(ApplicationOrm).where(
                        ApplicationOrm.user_id == user_id,
                    ).order_by(ApplicationOrm.id.desc()).limit(limit + 1)

                result = await session.execute(query)
                items = result.scalars().all()
                items.reverse()
                rows = items[:limit]
                next_id = rows[-1].id if cursor_id is not None and len(items) > limit else None
                prev_id = rows[0].id if len(items) > limit else None

            else:
                raise ValueError("Invalid direction")

            return rows, next_id, prev_id