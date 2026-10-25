"""
Правила каталога: сегмент компании, подходит ли продукт под заявку, подбор продукта
и условия предложения (ставка и платёж).

Всё здесь детерминировано и не зависит от ML: модель оценивает риск, а эти правила
решают, какой продукт и на каких условиях банк может предложить.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone


# Критерии микробизнеса по 209-ФЗ: до 15 сотрудников и до 120 млн ₽ выручки в год.
# Всё, что больше, считаем малым бизнесом (средний бизнес в MVP не выделяем).
MICRO_MAX_EMPLOYEES = 15
MICRO_MAX_REVENUE_RUB = 120_000_000

SEGMENT_NAME = {"micro": "микробизнес", "small": "малый бизнес"}
LEGAL_FORM_NAME = {"individual_entrepreneur": "ИП", "llc": "ООО", "joint_stock_company": "АО"}
PURPOSE_NAME = {
    "working_capital": "пополнение оборотных средств",
    "equipment": "покупка оборудования",
    "expansion": "развитие бизнеса",
    "refinancing": "рефинансирование",
    "other": "другие цели",
}

# Где в диапазоне ставок продукта стоит ставка для каждого грейда риска:
# A — нижняя граница, E — верхняя.
GRADE_RATE_POSITION = {"A": 0.0, "B": 0.25, "C": 0.5, "D": 0.75, "E": 1.0}


def derive_segment(employee_count: int, annual_revenue_rub: int) -> str:
    """Сегмент считает банк по данным компании, а не выбирает клиент"""
    if employee_count <= MICRO_MAX_EMPLOYEES and annual_revenue_rub <= MICRO_MAX_REVENUE_RUB:
        return "micro"
    return "small"


def company_age_months(registration_date: datetime, now: datetime | None = None) -> int:
    """Полных месяцев с даты регистрации компании"""
    now = now or datetime.now(timezone.utc)
    reg = registration_date if registration_date.tzinfo else registration_date.replace(tzinfo=timezone.utc)
    months = (now.year - reg.year) * 12 + (now.month - reg.month)
    if now.day < reg.day:
        months -= 1
    return max(months, 0)


@dataclass(frozen=True)
class Applicant:
    """Что нужно знать о заявке, чтобы понять, подходит ли продукт"""
    segment: str
    purpose: str
    amount_rub: int
    term_months: int
    legal_form: str
    age_months: int


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " ₽"


def mismatch_reasons(product, applicant: Applicant) -> list[str]:
    """Почему продукт не подходит под заявку. Пустой список — подходит"""
    reasons: list[str] = []
    if product.segment not in ("both", applicant.segment):
        reasons.append(f"только для сегмента «{SEGMENT_NAME.get(product.segment, product.segment)}»")
    if applicant.purpose not in (product.purposes or []):
        reasons.append(f"не подходит для цели «{PURPOSE_NAME.get(applicant.purpose, applicant.purpose)}»")
    if not product.min_amount_rub <= applicant.amount_rub <= product.max_amount_rub:
        reasons.append(f"сумма от {_money(product.min_amount_rub)} до {_money(product.max_amount_rub)}")
    if not product.min_term_months <= applicant.term_months <= product.max_term_months:
        reasons.append(f"срок от {product.min_term_months} до {product.max_term_months} мес.")
    extras = product.extras or {}
    forms = extras.get("legal_forms")
    if forms and applicant.legal_form not in forms:
        names = ", ".join(LEGAL_FORM_NAME.get(f, f) for f in forms)
        reasons.append(f"доступен только для: {names}")
    min_age = extras.get("min_company_age_months")
    if min_age and applicant.age_months < min_age:
        reasons.append(f"компания должна работать не меньше {min_age} мес.")
    return reasons


def pick_product(products, applicant: Applicant):
    """
    Подбирает продукт под заявку: из подходящих — с самой низкой ставкой,
    при равенстве — первый по порядку в каталоге. None — ничего не подходит.
    """
    fitting = [p for p in products if not mismatch_reasons(p, applicant)]
    if not fitting:
        return None
    return min(fitting, key=lambda p: (p.rate_min_percent, p.display_order))


def no_product_explanation(applicant: Applicant) -> str:
    """Текст для клиента, когда ни один продукт не подошёл"""
    return (
        "Под эти условия нет подходящего продукта: "
        f"{PURPOSE_NAME.get(applicant.purpose, applicant.purpose)}, {_money(applicant.amount_rub)} "
        f"на {applicant.term_months} мес., {SEGMENT_NAME.get(applicant.segment, applicant.segment)}. "
        "Попробуйте изменить сумму, срок или цель — или выберите продукт в каталоге."
    )


def offer_rate(product, risk_grade: str) -> float:
    """Ставка внутри диапазона продукта по грейду риска"""
    position = GRADE_RATE_POSITION.get(risk_grade, 1.0)
    rate = product.rate_min_percent + (product.rate_max_percent - product.rate_min_percent) * position
    return round(rate, 1)


def annuity_payment(amount_rub: int, rate_percent: float, term_months: int) -> int:
    """Ежемесячный аннуитетный платёж, ₽"""
    if term_months <= 0:
        return amount_rub
    monthly = rate_percent / 100 / 12
    if monthly == 0:
        return round(amount_rub / term_months)
    return round(amount_rub * monthly / (1 - (1 + monthly) ** -term_months))


def build_offer(product, amount_rub: int, term_months: int, risk_grade: str) -> dict:
    """Условия предложения: продукт, сумма, срок, ставка, платёж, общая сумма и переплата"""
    rate = offer_rate(product, risk_grade)
    payment = annuity_payment(amount_rub, rate, term_months)
    total = payment * term_months
    return {
        "product_type": product.product_type,
        "product_code": product.code,
        "product_name": product.name,
        "amount_rub": amount_rub,
        "term_months": term_months,
        "rate_percent": rate,
        "monthly_payment_rub": payment,
        "total_payment_rub": total,
        "overpayment_rub": total - amount_rub,
    }


def with_amount(applicant: Applicant, amount_rub: int) -> Applicant:
    """Та же заявка с другой суммой (для встречного предложения)"""
    return replace(applicant, amount_rub=amount_rub)
