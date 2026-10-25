from collections import Counter

from sqlalchemy import select

from database import new_session
from models.applications import ApplicationOrm


class AdminRepository:
    """Репозиторий для админских агрегатов по заявкам"""

    @classmethod
    async def list_all_paginated(
        cls,
        cursor_id: int | None,
        direction: str,
        limit: int,
        status: str | None = None,
        outcome: str | None = None,
    ) -> tuple[list[ApplicationOrm], int | None, int | None]:
        """Возвращает все заявки с курсорной пагинацией; можно отфильтровать по статусу и типу результата"""
        filters = []
        if status:
            filters.append(ApplicationOrm.status == status)
        if outcome:
            filters.append(ApplicationOrm.outcome == outcome)
        async with new_session() as session:
            if direction == "forward":
                if cursor_id is not None:
                    query = (
                        select(ApplicationOrm)
                        .where(ApplicationOrm.id > cursor_id, *filters)
                        .order_by(ApplicationOrm.id.asc())
                        .limit(limit + 1)
                    )
                else:
                    query = (
                        select(ApplicationOrm)
                        .where(*filters)
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
                        .where(ApplicationOrm.id < cursor_id, *filters)
                        .order_by(ApplicationOrm.id.desc())
                        .limit(limit + 1)
                    )
                else:
                    query = (
                        select(ApplicationOrm)
                        .where(*filters)
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

    @classmethod
    async def stats_overview(cls) -> dict:
        """Считает агрегаты по всем заявкам"""
        async with new_session() as session:
            result = await session.execute(select(ApplicationOrm))
            applications = result.scalars().all()

        by_status: Counter = Counter()
        by_product_type: Counter = Counter()
        by_risk_grade: Counter = Counter()
        by_outcome: Counter = Counter()
        by_decision: Counter = Counter()
        scores: list[int] = []

        for app in applications:
            by_status[app.status] += 1
            by_product_type[app.product_type or "unknown"] += 1
            if getattr(app, "outcome", None):
                by_outcome[app.outcome] += 1

            scoring = app.scoring_result
            if isinstance(scoring, dict):
                grade = scoring.get("risk_grade")
                score = scoring.get("score")
                decision = (scoring.get("decision") or {}).get("decision")
                if grade is not None:
                    by_risk_grade[grade] += 1
                if isinstance(score, (int, float)):
                    scores.append(int(score))
                if decision:
                    by_decision[decision] += 1

        avg_score = float(sum(scores) / len(scores)) if scores else None

        return {
            "total": len(applications),
            "by_status": dict(by_status),
            "by_product_type": dict(by_product_type),
            "by_risk_grade": dict(by_risk_grade),
            "by_outcome": dict(by_outcome),
            "by_decision": dict(by_decision),
            "avg_score": avg_score,
        }