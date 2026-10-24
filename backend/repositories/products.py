from sqlalchemy import select

from database import new_session
from models.products import ProductOrm


SEED_PRODUCTS = [
    {
        "code": "microloan",
        "name": "Микрозайм",
        "description": "Быстрый займ для микробизнеса без залога",
        "product_type": "microloan",
        "segment": "micro",
        "min_amount_rub": 50000,
        "max_amount_rub": 3000000,
        "min_term_months": 1,
        "max_term_months": 24,
        "rate_min_percent": 18.0,
        "rate_max_percent": 28.0,
        "purposes": ["working_capital", "equipment", "other"],
        "features": ["Без залога", "Решение за 1 день"],
        "requirements": ["ИП или ООО от 6 месяцев"],
        "extras": {"express_decision": True},
        "display_order": 1,
    },
    {
        "code": "working_capital",
        "name": "Оборотный кредит",
        "description": "Финансирование текущей деятельности компании",
        "product_type": "term_loan",
        "segment": "small",
        "min_amount_rub": 100000,
        "max_amount_rub": 30000000,
        "min_term_months": 3,
        "max_term_months": 36,
        "rate_min_percent": 15.0,
        "rate_max_percent": 24.0,
        "purposes": ["working_capital", "expansion"],
        "features": ["Гибкий график платежей"],
        "requirements": ["ООО от 12 месяцев"],
        "extras": {"revolving": True},
        "display_order": 2,
    },
    {
        "code": "overdraft",
        "name": "Овердрафт",
        "description": "Краткосрочное финансирование кассовых разрывов",
        "product_type": "overdraft",
        "segment": "small",
        "min_amount_rub": 500000,
        "max_amount_rub": 15000000,
        "min_term_months": 6,
        "max_term_months": 12,
        "rate_min_percent": 14.0,
        "rate_max_percent": 22.0,
        "purposes": ["working_capital"],
        "features": ["Автоматическое погашение"],
        "requirements": ["Расчётный счёт в банке от 6 месяцев"],
        "extras": {"limit_period_days": 180, "repayment_method": "auto"},
        "display_order": 3,
    },
    {
        "code": "credit_line",
        "name": "Кредитная линия",
        "description": "Возобновляемая линия с выборкой траншами",
        "product_type": "credit_line",
        "segment": "small",
        "min_amount_rub": 1000000,
        "max_amount_rub": 50000000,
        "min_term_months": 12,
        "max_term_months": 36,
        "rate_min_percent": 13.0,
        "rate_max_percent": 20.0,
        "purposes": ["working_capital", "expansion", "equipment"],
        "features": ["Выборка траншами"],
        "requirements": ["ООО от 24 месяцев"],
        "extras": {"tranche_min_rub": 100000},
        "display_order": 4,
    },
    {
        "code": "leasing",
        "name": "Лизинг оборудования",
        "description": "Покупка оборудования в рассрочку",
        "product_type": "leasing",
        "segment": "small",
        "min_amount_rub": 500000,
        "max_amount_rub": 40000000,
        "min_term_months": 12,
        "max_term_months": 60,
        "rate_min_percent": 12.0,
        "rate_max_percent": 20.0,
        "purposes": ["equipment", "expansion"],
        "features": ["Аванс от 10%"],
        "requirements": ["ООО или ИП от 12 месяцев"],
        "extras": {
            "advance_percent_min": 10,
            "advance_percent_max": 30,
            "equipment_types": ["станки", "транспорт"],
        },
        "display_order": 5,
    },
]


class ProductRepository:
    """Репозиторий для работы с каталогом кредитных продуктов"""

    @classmethod
    async def ensure_products(cls) -> None:
        """Идемпотентно создаёт продукты из сида если их ещё нет"""
        async with new_session() as session:
            for item in SEED_PRODUCTS:
                query = select(ProductOrm).where(ProductOrm.code == item["code"])
                result = await session.execute(query)
                if result.scalars().first():
                    continue
                session.add(ProductOrm(**item))
            await session.commit()

    @classmethod
    async def list_active(cls) -> list[ProductOrm]:
        """Возвращает активные продукты, отсортированные по display_order"""
        async with new_session() as session:
            query = (
                select(ProductOrm)
                .where(ProductOrm.is_active.is_(True))
                .order_by(ProductOrm.display_order.asc())
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    @classmethod
    async def get_by_code(cls, code: str) -> ProductOrm | None:
        """Возвращает продукт по slug-коду"""
        async with new_session() as session:
            query = select(ProductOrm).where(ProductOrm.code == code)
            result = await session.execute(query)
            return result.scalars().first()