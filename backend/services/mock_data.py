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
TAX_REGIMES = ("УСН", "ОСН", "ПАТЕНТ", "ЕСХН")
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


def _random_ogrn(rng: random.Random) -> str:
    """Генерирует 13-значный ОГРН из seed"""
    return "1" + "".join(str(rng.randint(0, 9)) for _ in range(12))


def generate_egrul(inn: str, now: datetime | None = None) -> SEgrulResponse:
    """Генерирует детерминированный ответ ЕГРЮЛ по ИНН"""
    now = now or datetime.now(timezone.utc)
    rng = _seed(inn, "egrul")
    legal_form = rng.choice(LEGAL_FORMS)
    okved, okved_desc = rng.choice(OKVED_LIST)
    region = rng.choice(REGIONS)
    return SEgrulResponse(
        inn=inn,
        ogrn=_random_ogrn(rng),
        legal_name=f"{LEGAL_FORM_PREFIX[legal_form]} Компания {inn[-4:]}",
        legal_form=legal_form,
        status="active",
        okved=okved,
        okved_description=okved_desc,
        region=region,
        registration_date=_ago(rng.randint(180, 4000), now),
        employee_count=rng.randint(1, 200),
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
        tax_regime=rng.choice(TAX_REGIMES),
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
    return SBkiResponse(
        inn=inn,
        credit_score=rng.randint(300, 850),
        active_obligations_count=active,
        total_outstanding_rub=rng.randint(0, 10_000_000),
        monthly_debt_payments_rub=rng.randint(0, 500_000) if active else 0,
        max_days_past_due_12m=rng.choice((0, 0, 0, rng.randint(1, 90))),
        has_current_past_due=rng.random() < 0.1,
        credit_utilization=round(rng.uniform(0.0, 0.95), 2),
        closed_obligations_count=rng.randint(0, 10),
        applications_last_6m=rng.randint(0, 8),
        last_update=_ago(rng.randint(1, 30), now),
    )