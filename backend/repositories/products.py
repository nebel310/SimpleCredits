from sqlalchemy import select

from database import new_session
from models.products import ProductOrm


# Версия условий каталога. Когда условия меняются (ставки, границы, цели, требования),
# версия увеличивается, и ensure_products обновляет их в уже существующей базе.
# Название, описание, порядок и активность продукта при этом не трогаются.
#
# Ставки: ключевая ставка Банка России — 14% (сохранена 23.10.2026). Нижняя граница
# каждого продукта — ключевая + надбавка за риск сегмента и продукта (от 3 п.п.).
# Требования к компании (форма и возраст) заданы полями в extras, чтобы их можно было проверять.
SEED_VERSION = 2

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
        "rate_min_percent": 22.0,
        "rate_max_percent": 32.0,
        "purposes": ["working_capital", "equipment", "other"],
        "features": ["Без залога", "Решение сразу после проверки"],
        "requirements": ["ИП или ООО, работает от 6 месяцев", "Только микробизнес"],
        "extras": {
            "express_decision": True,
            "legal_forms": ["individual_entrepreneur", "llc"],
            "min_company_age_months": 6,
        },
        "display_order": 1,
    },
    {
        "code": "working_capital",
        "name": "Оборотный кредит",
        "description": "Финансирование текущей деятельности и рефинансирование долгов",
        "product_type": "term_loan",
        "segment": "both",
        "min_amount_rub": 100000,
        "max_amount_rub": 30000000,
        "min_term_months": 3,
        "max_term_months": 36,
        "rate_min_percent": 18.0,
        "rate_max_percent": 25.0,
        "purposes": ["working_capital", "expansion", "refinancing", "other"],
        "features": ["Гибкий график платежей"],
        "requirements": ["ИП, ООО или АО, работает от 12 месяцев"],
        "extras": {
            "revolving": True,
            "legal_forms": ["individual_entrepreneur", "llc", "joint_stock_company"],
            "min_company_age_months": 12,
        },
        "display_order": 2,
    },
    {
        "code": "overdraft",
        "name": "Овердрафт",
        "description": "Краткосрочное финансирование кассовых разрывов",
        "product_type": "overdraft",
        "segment": "both",
        "min_amount_rub": 500000,
        "max_amount_rub": 15000000,
        "min_term_months": 6,
        "max_term_months": 12,
        "rate_min_percent": 19.0,
        "rate_max_percent": 26.0,
        "purposes": ["working_capital"],
        "features": ["Автоматическое погашение"],
        "requirements": ["ИП, ООО или АО, работает от 6 месяцев"],
        "extras": {
            "limit_period_days": 180,
            "repayment_method": "auto",
            "legal_forms": ["individual_entrepreneur", "llc", "joint_stock_company"],
            "min_company_age_months": 6,
        },
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
        "rate_min_percent": 17.5,
        "rate_max_percent": 24.0,
        "purposes": ["working_capital", "expansion", "equipment"],
        "features": ["Выборка траншами"],
        "requirements": ["ООО или АО, работает от 24 месяцев", "Только малый бизнес"],
        "extras": {
            "tranche_min_rub": 100000,
            "legal_forms": ["llc", "joint_stock_company"],
            "min_company_age_months": 24,
        },
        "display_order": 4,
    },
    {
        "code": "leasing",
        "name": "Лизинг оборудования",
        "description": "Покупка оборудования в рассрочку",
        "product_type": "leasing",
        "segment": "both",
        "min_amount_rub": 500000,
        "max_amount_rub": 40000000,
        "min_term_months": 12,
        "max_term_months": 60,
        "rate_min_percent": 17.0,
        "rate_max_percent": 23.0,
        "purposes": ["equipment", "expansion"],
        "features": ["Аванс от 10%"],
        "requirements": ["ИП, ООО или АО, работает от 12 месяцев"],
        "extras": {
            "advance_percent_min": 10,
            "advance_percent_max": 30,
            "equipment_types": ["станки", "транспорт"],
            "legal_forms": ["individual_entrepreneur", "llc", "joint_stock_company"],
            "min_company_age_months": 12,
        },
        "display_order": 5,
    },
]

# Поля условий, которые обновляются при смене SEED_VERSION
CONDITION_FIELDS = (
    "segment", "min_amount_rub", "max_amount_rub", "min_term_months", "max_term_months",
    "rate_min_percent", "rate_max_percent", "purposes", "features", "requirements", "extras",
)


class ProductRepository:
    """Репозиторий для работы с каталогом кредитных продуктов"""

    @classmethod
    async def ensure_products(cls) -> None:
        """
        Идемпотентно создаёт продукты из сида. Если в базе продукт из старой версии
        сида (extras.seed_version меньше SEED_VERSION), обновляет его условия:
        ставки, границы, цели, требования. Название, описание, порядок и активность
        не трогаются — ручные правки сохраняются.
        """
        async with new_session() as session:
            for item in SEED_PRODUCTS:
                seed = {**item, "extras": {**item["extras"], "seed_version": SEED_VERSION}}
                query = select(ProductOrm).where(ProductOrm.code == item["code"])
                result = await session.execute(query)
                product = result.scalars().first()
                if product is None:
                    session.add(ProductOrm(**seed))
                    continue
                if (product.extras or {}).get("seed_version", 1) < SEED_VERSION:
                    for field in CONDITION_FIELDS:
                        setattr(product, field, seed[field])
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