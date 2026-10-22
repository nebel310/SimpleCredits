from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

from rawdata.constants import (
    COMPANY_STEMS,
    COMPANY_SUFFIXES,
    FIRST_NAMES_F,
    FIRST_NAMES_M,
    LAST_NAMES_F,
    LAST_NAMES_M,
    LEGAL_FORM_LABELS,
    NOW,
    PATRONYMICS_F,
    PATRONYMICS_M,
    STREETS,
)

INN10_WEIGHTS = [2, 4, 10, 3, 5, 9, 4, 6, 8]
INN12_CHECK1_WEIGHTS = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
INN12_CHECK2_WEIGHTS = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
VIN_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
PLATE_ALPHABET = "АВЕКМНОРСТУХ"


def make_rng(seed: int, name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{name}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def iso_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_date(value: datetime) -> str:
    return iso_dt(value)[:10]


def random_dt(rng: random.Random, start: datetime, end: datetime) -> datetime:
    if end <= start:
        return start
    seconds = (end - start).total_seconds()
    return start + timedelta(seconds=rng.uniform(0, seconds))


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, 28)
    return value.replace(year=year, month=month, day=day)


def month_starts(count: int, end: datetime = NOW) -> list[datetime]:
    current = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return [add_months(current, -offset) for offset in range(count - 1, -1, -1)]


def period_label(value: datetime) -> str:
    return value.strftime("%Y-%m")


def month_end(value: datetime) -> datetime:
    return add_months(value.replace(day=1), 1) - timedelta(seconds=1)


def random_date_in_month(rng: random.Random, month_start: datetime) -> datetime:
    end = month_end(month_start)
    return random_dt(rng, month_start, end)


def weighted_choice(rng: random.Random, options: list, weights: list[float]):
    return rng.choices(options, weights=weights, k=1)[0]


def make_inn10(rng: random.Random) -> str:
    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]
    check = sum(value * weight for value, weight in zip(digits, INN10_WEIGHTS)) % 11 % 10
    return "".join(str(value) for value in digits) + str(check)


def make_inn12(rng: random.Random) -> str:
    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(9)]
    check1 = sum(
        value * weight for value, weight in zip(digits, INN12_CHECK1_WEIGHTS)
    ) % 11 % 10
    digits.append(check1)
    check2 = sum(
        value * weight for value, weight in zip(digits, INN12_CHECK2_WEIGHTS)
    ) % 11 % 10
    digits.append(check2)
    return "".join(str(value) for value in digits)


def make_inn(rng: random.Random, legal_form: str) -> str:
    return make_inn12(rng) if legal_form == "ip" else make_inn10(rng)


def make_ogrn(rng: random.Random, legal_form: str, region_code: str, year: int) -> str:
    if legal_form == "ip":
        serial = "".join(str(rng.randint(0, 9)) for _ in range(9))
        body = f"3{year % 100:02d}{region_code}{serial}"
        check = int(body) % 13 % 10
        return body + str(check)
    serial = "".join(str(rng.randint(0, 9)) for _ in range(7))
    body = f"1{year % 100:02d}{region_code}{serial}"
    check = int(body) % 11 % 10
    return body + str(check)


def make_kpp(rng: random.Random, region_code: str) -> str:
    return f"{region_code}01{rng.randint(1, 99):02d}{rng.randint(1, 999):03d}"


def make_account(rng: random.Random) -> str:
    return "40802" + "".join(str(rng.randint(0, 9)) for _ in range(15))


def make_phone(rng: random.Random) -> str:
    return f"+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"


def make_email(idx: int) -> str:
    return f"info@company{idx:04d}.example.com"


def make_website(idx: int) -> str:
    return f"https://company{idx:04d}.example.com"


def make_person_name(rng: random.Random, female: bool = False) -> dict:
    if female:
        last_name = rng.choice(LAST_NAMES_F)
        first_name = rng.choice(FIRST_NAMES_F)
        patronymic = rng.choice(PATRONYMICS_F)
    else:
        last_name = rng.choice(LAST_NAMES_M)
        first_name = rng.choice(FIRST_NAMES_M)
        patronymic = rng.choice(PATRONYMICS_M)
    return {
        "last_name": last_name,
        "first_name": first_name,
        "patronymic": patronymic,
        "full_name": f"{last_name} {first_name} {patronymic}",
        "initials": f"{first_name[0]}.{patronymic[0]}.",
        "gender": "female" if female else "male",
    }


def make_company_name(
    rng: random.Random, legal_form: str, idx: int, person: dict | None = None
) -> tuple[str, str]:
    if legal_form == "ip":
        name = person or make_person_name(rng)
        short_name = f"ИП {name['last_name']} {name['initials']}"
        return short_name, short_name
    prefix = LEGAL_FORM_LABELS[legal_form]
    stem = rng.choice(COMPANY_STEMS)
    if rng.random() < 0.65:
        stem = f"{stem} {rng.choice(COMPANY_SUFFIXES)}"
    short_name = f"{prefix} «{stem}»"
    return short_name, short_name


def make_address(rng: random.Random, city: str) -> str:
    street = rng.choice(STREETS)
    building = rng.randint(1, 120)
    office = rng.randint(1, 400)
    return f"г. {city}, ул. {street}, д. {building}, офис {office}"


def make_cadastral(rng: random.Random, region_code: str) -> str:
    return f"{region_code}:{rng.randint(1, 99):02d}:{rng.randint(1, 999999):06d}:{rng.randint(1, 9999)}"


def make_vin(rng: random.Random) -> str:
    return "".join(rng.choice(VIN_ALPHABET) for _ in range(17))


def make_plate(rng: random.Random, region_code: str) -> str:
    letters = "".join(rng.choice(PLATE_ALPHABET) for _ in range(2))
    return f"{rng.choice(PLATE_ALPHABET)}{rng.randint(100, 999)}{letters}{region_code}"


def annuity_payment(amount: float, annual_rate: float, months: int) -> float:
    monthly_rate = annual_rate / 100.0 / 12.0
    if monthly_rate == 0:
        return amount / months
    return amount * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-months))


def payment_schedule(
    amount: float, annual_rate: float, months: int, start: datetime
) -> list[dict]:
    payment = annuity_payment(amount, annual_rate, months)
    monthly_rate = annual_rate / 100.0 / 12.0
    balance = amount
    schedule = []
    for index in range(months):
        interest = balance * monthly_rate
        principal = payment - interest
        balance = max(0.0, balance - principal)
        schedule.append(
            {
                "payment_number": index + 1,
                "payment_date": iso_date(add_months(start, index + 1)),
                "amount_rub": round(payment, 2),
                "principal_rub": round(principal, 2),
                "interest_rub": round(interest, 2),
                "balance_rub": round(balance, 2),
            }
        )
    return schedule
