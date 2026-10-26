import hashlib
import random
from datetime import datetime, timedelta, timezone

from schemas.mock import SBkiResponse, SEgrulResponse, SFnsResponse


LEGAL_FORMS = ("llc", "individual_entrepreneur", "joint_stock_company")
LEGAL_FORM_PREFIX = {"llc": "ООО", "individual_entrepreneur": "ИП", "joint_stock_company": "АО"}
OKVED_LIST = (
    ("62.01", "Разработка компьютерного программного обеспечения"),
    ("46.90", "Торговля оптовая неспециализированная"),
    ("49.41", "Деятельность автомобильного грузового транспорта"),
    ("56.10", "Деятельность ресторанов и услуги по доставке продуктов питания"),
    ("43.21", "Производство электромонтажных работ"),
)
REGIONS = ("Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань")
# Режимы налогообложения по форме: патент бывает только у ИП, ЕСХН — только у
# сельхозпроизводителей (в моках таких ОКВЭД нет, поэтому не используем)
TAX_REGIMES_IP = ("УСН", "ПАТЕНТ", "ОСН")
TAX_REGIMES_LEGAL = ("УСН", "ОСН")
DIRECTORS = (
    "Иванов Иван Иванович",
    "Петров Пётр Петрович",
    "Сидоров Сидор Сидорович",
    "Кузнецова Анна Сергеевна",
    "Смирнов Алексей Владимирович",
)


def is_valid_inn(inn: str) -> bool:
    """Проверяет что ИНН — 10 или 12 цифр"""
    return bool(inn) and inn.isdigit() and len(inn) in (10, 12)


def _seed(inn: str, salt: str) -> random.Random:
    """Возвращает Random, засиженный от sha256(inn:salt)"""
    digest = hashlib.sha256(f"{inn}:{salt}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _ago(days: int, now: datetime) -> datetime:
    """Возвращает момент в UTC, сдвинутый на days дней назад от now"""
    return now - timedelta(days=days)


def _random_ogrn(rng: random.Random, legal_form: str) -> str:
    """ОГРН юрлица — 13 цифр и начинается с 1, ОГРНИП предпринимателя — 15 цифр и начинается с 3"""
    if legal_form == "individual_entrepreneur":
        return "3" + "".join(str(rng.randint(0, 9)) for _ in range(14))
    return "1" + "".join(str(rng.randint(0, 9)) for _ in range(12))


def legal_form_by_inn(inn: str, rng: random.Random) -> str:
    """ИНН из 12 цифр — у ИП, из 10 — у организации (ООО чаще, АО реже)"""
    if len(inn) == 12:
        return "individual_entrepreneur"
    return "joint_stock_company" if rng.random() < 0.15 else "llc"


def generate_egrul(inn: str, now: datetime | None = None) -> SEgrulResponse:
    """Генерирует детерминированный ответ ЕГРЮЛ по ИНН"""
    now = now or datetime.now(timezone.utc)
    rng = _seed(inn, "egrul")
    legal_form = legal_form_by_inn(inn, rng)
    okved, okved_desc = rng.choice(OKVED_LIST)
    region = rng.choice(REGIONS)
    return SEgrulResponse(
        inn=inn,
        ogrn=_random_ogrn(rng, legal_form),
        legal_name=f"{LEGAL_FORM_PREFIX[legal_form]} Компания {inn[-4:]}",
        legal_form=legal_form,
        status="active",
        okved=okved,
        okved_description=okved_desc,
        region=region,
        registration_date=_ago(rng.randint(180, 4000), now),
        employee_count=rng.randint(1, 15) if legal_form == "individual_entrepreneur" else rng.randint(1, 200),
        director=rng.choice(DIRECTORS),
        address=f"г. {region}, ул. Тестовая, д. {rng.randint(1, 100)}",
    )


def generate_fns(inn: str, now: datetime | None = None) -> SFnsResponse:
    """Генерирует детерминированный ответ ФНС по ИНН"""
    now = now or datetime.now(timezone.utc)
    rng = _seed(inn, "fns")
    has_debt = rng.random() < 0.2
    return SFnsResponse(
        inn=inn,
        tax_regime=rng.choice(TAX_REGIMES_IP if len(inn) == 12 else TAX_REGIMES_LEGAL),
        tax_debt_rub=rng.randint(1000, 500_000) if has_debt else 0,
        disqualified_persons=False,
        mass_address=rng.random() < 0.05,
        mass_director=rng.random() < 0.05,
        reliability_score=rng.randint(40, 100),
        last_reporting_date=_ago(rng.randint(30, 200), now),
    )


def generate_bki(inn: str, now: datetime | None = None) -> SBkiResponse:
    """Генерирует детерминированный ответ БКИ по ИНН"""
    now = now or datetime.now(timezone.utc)
    rng = _seed(inn, "bki")
    active = rng.randint(0, 5)
    # Остаток долга есть только при действующих кредитах, платёж — 3–8% остатка в месяц,
    # текущая просрочка возможна только при действующих кредитах и тогда видна в истории
    outstanding = rng.randint(300_000, 10_000_000) if active else 0
    payments = round(outstanding * rng.uniform(0.03, 0.08)) if active else 0
    current_past_due = bool(active) and rng.random() < 0.1
    max_dpd = rng.randint(1, 90) if current_past_due else rng.choice((0, 0, 0, rng.randint(1, 90)))
    return SBkiResponse(
        inn=inn,
        credit_score=rng.randint(300, 850),
        active_obligations_count=active,
        total_outstanding_rub=outstanding,
        monthly_debt_payments_rub=payments,
        max_days_past_due_12m=max_dpd,
        has_current_past_due=current_past_due,
        credit_utilization=round(rng.uniform(0.05, 0.95), 2) if active else 0.0,
        closed_obligations_count=rng.randint(0, 10),
        applications_last_6m=rng.randint(0, 8),
        last_update=_ago(rng.randint(1, 30), now),
    )