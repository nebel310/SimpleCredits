from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from rawdata import constants as C
from rawdata.identifiers import (
    add_months,
    annuity_payment,
    clamp,
    iso_date,
    iso_dt,
    make_account,
    make_address,
    make_cadastral,
    make_company_name,
    make_email,
    make_inn,
    make_kpp,
    make_ogrn,
    make_person_name,
    make_phone,
    make_plate,
    make_rng,
    make_vin,
    make_website,
    month_starts,
    payment_schedule,
    period_label,
    random_date_in_month,
    random_dt,
    weighted_choice,
)
from rawdata.schema import TABLE_ORDER


@dataclass
class User:
    user_id: str
    company_id: str
    role: str
    full_name: str
    birth_date: str
    inn: str
    phone: str
    email: str
    position: str
    is_signer: int
    is_beneficial_owner: int


@dataclass
class Company:
    company_id: str
    idx: int
    legal_form: str
    segment: str
    legal_name: str
    short_name: str
    inn: str
    ogrn: str
    kpp: str
    registration_date: datetime
    status: str
    region: dict
    address: str
    okved: dict
    employee_count: int
    annual_revenue_rub: int
    monthly_revenue_rub: float
    monthly_expenses_rub: float
    total_debt_rub: float
    net_profit_rub: float
    ebitda_rub: float
    cash_rub: float
    receivables_rub: float
    inventory_rub: float
    quality: float
    risk: float
    discipline: float
    credit_utilization: float
    past_due_days: int
    current_past_due: int
    tax_regime: str
    website: str
    phone: str
    email: str
    has_acquiring: bool
    has_marketplace: bool
    has_site: bool
    has_property: bool
    has_vehicles: bool
    has_license: bool
    has_tenders: bool
    has_export: bool
    users: list[User] = field(default_factory=list)
    bank_products: list[dict] = field(default_factory=list)


def next_id(counters: dict[str, int], key: str, prefix: str, width: int) -> str:
    counters[key] = counters.get(key, 0) + 1
    return f"{prefix}{counters[key]:0{width}d}"


def int_rub(value: float) -> int:
    return int(max(0, round(value)))


def make_company(
    rng,
    idx: int,
    used_inn: set[str],
    used_ogrn: set[str],
) -> Company:
    legal_form = weighted_choice(rng, C.LEGAL_FORMS, [0.70, 0.25, 0.05])
    if legal_form == "ip":
        segment = weighted_choice(rng, C.SEGMENTS, [0.85, 0.15])
    else:
        segment = weighted_choice(rng, C.SEGMENTS, [0.55, 0.45])

    person = make_person_name(rng, female=rng.random() < 0.35)
    legal_name, short_name = make_company_name(rng, legal_form, idx, person)
    region = rng.choice(C.REGIONS)
    okved = rng.choice(C.OKVED_PROFILES)

    quality = clamp(rng.gauss(0.0, 0.8), -2.5, 2.5)
    risk = clamp(
        0.12
        + 0.25 * okved["risk"]
        + 0.15 * region["risk"]
        - 0.05 * quality
        + rng.gauss(0.0, 0.08),
        0.01,
        0.90,
    )
    discipline = clamp(0.93 + 0.04 * quality + rng.gauss(0.0, 0.04), 0.35, 0.995)

    if segment == "micro":
        employee_count = int(clamp(rng.lognormvariate(1.7, 0.7), 1, 15))
        annual_revenue = int(clamp(rng.lognormvariate(15.0, 0.9), 500_000, 80_000_000))
    else:
        employee_count = int(clamp(rng.lognormvariate(3.7, 0.6), 15, 150))
        annual_revenue = int(clamp(rng.lognormvariate(17.2, 0.75), 20_000_000, 800_000_000))

    young = rng.random() < 0.15
    age_months = rng.randint(6, 24) if young else rng.randint(36, 180)
    registration_date = C.NOW - timedelta(days=age_months * 30)

    if idx % 37 == 0:
        status = "bankrupt"
    elif rng.random() < 0.12:
        status = "liquidating"
    elif risk > 0.55 and rng.random() < 0.25:
        status = "bankrupt"
    elif rng.random() < 0.03:
        status = "reorganized"
    else:
        status = "active"
    if status != "active":
        annual_revenue = int(annual_revenue * rng.uniform(0.30, 0.80))

    monthly_revenue = annual_revenue / 12.0 * rng.uniform(0.85, 1.15)
    monthly_expenses = monthly_revenue * clamp(
        0.72 + 0.22 * risk + rng.gauss(0.0, 0.06), 0.55, 1.05
    )
    total_debt = annual_revenue * clamp(
        0.05 + 0.40 * risk + rng.gauss(0.0, 0.10), 0.0, 1.8
    )
    net_profit = annual_revenue * clamp(
        0.08 - 0.12 * risk + 0.02 * quality + rng.gauss(0.0, 0.05), -0.30, 0.35
    )
    ebitda = annual_revenue * clamp(
        0.12 - 0.10 * risk + 0.02 * quality + rng.gauss(0.0, 0.05), -0.20, 0.40
    )
    cash = monthly_revenue * clamp(rng.lognormvariate(-0.6, 0.6), 0.02, 3.0)
    receivables = monthly_revenue * clamp(rng.lognormvariate(-0.2, 0.6), 0.05, 3.0)
    inventory = 0.0
    if okved["industry"] in {"Ритейл", "Опт", "Производство", "HoReCa"}:
        inventory = monthly_revenue * clamp(rng.lognormvariate(-0.2, 0.7), 0.05, 3.0)

    credit_utilization = clamp(0.15 + 0.75 * risk + rng.gauss(0.0, 0.10), 0.05, 1.0)

    current_past_due = int(rng.random() < clamp(risk * 0.30, 0.0, 0.30))
    if current_past_due:
        past_due_days = rng.choice([5, 10, 15, 30, 45, 60, 90])
    elif rng.random() < clamp(risk * 0.35, 0.0, 0.40):
        past_due_days = rng.choice([0, 5, 10, 15, 30, 60])
    else:
        past_due_days = 0

    if okved["industry"] == "Сельское хозяйство":
        tax_regime = weighted_choice(rng, ["eshn", "usn", "osn"], [0.35, 0.50, 0.15])
    elif legal_form == "ip":
        tax_regime = weighted_choice(rng, ["patent", "usn", "osn"], [0.25, 0.60, 0.15])
    else:
        tax_regime = weighted_choice(rng, ["osn", "usn", "eshn"], [0.35, 0.60, 0.05])

    has_site = rng.random() < 0.75
    has_acquiring = rng.random() < (
        0.65 if okved["industry"] in {"Ритейл", "HoReCa", "Бытовые услуги"} else 0.15
    )
    has_marketplace = rng.random() < (
        0.45 if okved["industry"] in {"Ритейл", "Опт", "Производство"} else 0.05
    )
    has_property = rng.random() < (0.40 if segment == "small" else 0.15)
    has_vehicles = rng.random() < 0.50
    has_license = rng.random() < (
        0.40 if okved["industry"] in C.LICENSE_TYPES else 0.08
    )
    has_tenders = rng.random() < (0.30 if segment == "small" else 0.10)
    has_export = rng.random() < 0.08

    inn = make_inn(rng, legal_form)
    while inn in used_inn:
        inn = make_inn(rng, legal_form)
    used_inn.add(inn)
    ogrn = make_ogrn(rng, legal_form, region["code"], registration_date.year)
    while ogrn in used_ogrn:
        ogrn = make_ogrn(rng, legal_form, region["code"], registration_date.year)
    used_ogrn.add(ogrn)
    kpp = make_kpp(rng, region["code"])

    return Company(
        company_id=f"C{idx:04d}",
        idx=idx,
        legal_form=legal_form,
        segment=segment,
        legal_name=legal_name,
        short_name=short_name,
        inn=inn,
        ogrn=ogrn,
        kpp=kpp,
        registration_date=registration_date,
        status=status,
        region=region,
        address=make_address(rng, region["city"]),
        okved=okved,
        employee_count=employee_count,
        annual_revenue_rub=annual_revenue,
        monthly_revenue_rub=monthly_revenue,
        monthly_expenses_rub=monthly_expenses,
        total_debt_rub=total_debt,
        net_profit_rub=net_profit,
        ebitda_rub=ebitda,
        cash_rub=cash,
        receivables_rub=receivables,
        inventory_rub=inventory,
        quality=quality,
        risk=risk,
        discipline=discipline,
        credit_utilization=credit_utilization,
        past_due_days=past_due_days,
        current_past_due=current_past_due,
        tax_regime=tax_regime,
        website=make_website(idx) if has_site else "",
        phone=make_phone(rng),
        email=make_email(idx),
        has_acquiring=has_acquiring,
        has_marketplace=has_marketplace,
        has_site=has_site,
        has_property=has_property,
        has_vehicles=has_vehicles,
        has_license=has_license,
        has_tenders=has_tenders,
        has_export=has_export,
    )


def company_row(company: Company) -> dict:
    return {
        "company_id": company.company_id,
        "inn": company.inn,
        "ogrn": company.ogrn,
        "kpp": company.kpp,
        "legal_name": company.legal_name,
        "short_name": company.short_name,
        "legal_form": company.legal_form,
        "segment": company.segment,
        "status": company.status,
        "registration_date": iso_date(company.registration_date),
        "region": company.region["name"],
        "city": company.region["city"],
        "address": company.address,
        "okved_main": company.okved["code"],
        "okved_name": company.okved["name"],
        "industry": company.okved["industry"],
        "employee_count": company.employee_count,
        "annual_revenue_rub": company.annual_revenue_rub,
        "website": company.website,
        "phone": company.phone,
        "email": company.email,
        "tax_regime": company.tax_regime,
        "created_at": iso_dt(C.NOW - timedelta(days=30)),
    }


def make_users(company: Company, rng, counters: dict[str, int]) -> list[User]:
    users = []
    owner_person = make_person_name(rng, female=rng.random() < 0.35)
    roles = []
    if company.legal_form == "ip":
        roles.append(("individual_entrepreneur", "Индивидуальный предприниматель", 1, 1))
    else:
        roles.append(("director", "Генеральный директор", 1, 1))
        if rng.random() < 0.45:
            roles.append(("owner", "Собственник", 0, 1))
    if rng.random() < 0.75:
        roles.append(("accountant", "Главный бухгалтер", 0, 0))
    if rng.random() < 0.25:
        roles.append(("finance_manager", "Финансовый менеджер", 0, 0))

    used_names = set()
    for role, position, is_signer, is_owner in roles:
        person = owner_person if role in {"individual_entrepreneur", "director"} else make_person_name(
            rng, female=rng.random() < 0.55
        )
        if person["full_name"] in used_names:
            person = make_person_name(rng, female=rng.random() < 0.55)
        used_names.add(person["full_name"])
        birth_year = rng.randint(1965, 2000)
        user = User(
            user_id=next_id(counters, "user", "U", 5),
            company_id=company.company_id,
            role=role,
            full_name=person["full_name"],
            birth_date=f"{birth_year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            inn=make_inn(rng, "ip"),
            phone=make_phone(rng),
            email=f"user{counters['user']:05d}@example.com",
            position=position,
            is_signer=is_signer,
            is_beneficial_owner=is_owner,
        )
        users.append(user)
    return users


def make_founders_and_managers(
    company: Company, rng, counters: dict[str, int], tables: dict
) -> None:
    founders = []
    if company.legal_form == "ip":
        owner = company.users[0]
        founders.append(
            {
                "founder_id": next_id(counters, "founder", "F", 5),
                "company_id": company.company_id,
                "founder_type": "individual_entrepreneur",
                "name": owner.full_name,
                "inn": owner.inn,
                "share_percent": 100.0,
                "is_beneficial_owner": 1,
                "since_date": iso_date(company.registration_date),
            }
        )
    else:
        count = rng.choices([1, 2, 3], weights=[0.6, 0.3, 0.1], k=1)[0]
        weights = [rng.uniform(0.1, 1.0) for _ in range(count)]
        total = sum(weights)
        shares = [round(weight / total * 100, 2) for weight in weights]
        shares[-1] = round(100.0 - sum(shares[:-1]), 2)
        for index, share in enumerate(shares):
            legal_entity = index > 0 and rng.random() < 0.25
            if legal_entity:
                name = f"ООО «Инвест-{index + 1}»"
                founder_type = "legal_entity"
                inn = make_inn(rng, "llc")
            else:
                person = make_person_name(rng, female=rng.random() < 0.4)
                name = person["full_name"]
                founder_type = "individual"
                inn = make_inn(rng, "ip")
            founders.append(
                {
                    "founder_id": next_id(counters, "founder", "F", 5),
                    "company_id": company.company_id,
                    "founder_type": founder_type,
                    "name": name,
                    "inn": inn,
                    "share_percent": share,
                    "is_beneficial_owner": int(index == 0 or share >= 25),
                    "since_date": iso_date(company.registration_date),
                }
            )

    for founder in founders:
        tables["founders"].append(founder)

    director = company.users[0]
    manager = {
        "manager_id": next_id(counters, "manager", "M", 5),
        "company_id": company.company_id,
        "full_name": director.full_name,
        "position": director.position,
        "inn": director.inn,
        "since_date": iso_date(company.registration_date),
        "is_disqualified": int(company.risk > 0.55 and rng.random() < 0.08),
    }
    tables["managers"].append(manager)


def make_consents(company: Company, rng, counters: dict[str, int], tables: dict) -> None:
    for user in company.users:
        for consent_type in C.CONSENT_TYPES:
            if rng.random() < 0.85:
                granted_at = random_dt(
                    rng,
                    C.NOW - timedelta(days=365),
                    C.NOW - timedelta(days=1),
                )
                status = "revoked" if rng.random() < 0.05 else "granted"
                tables["consents"].append(
                    {
                        "consent_id": next_id(counters, "consent", "CN", 6),
                        "user_id": user.user_id,
                        "company_id": company.company_id,
                        "consent_type": consent_type,
                        "granted_at": iso_dt(granted_at),
                        "expires_at": iso_dt(granted_at + timedelta(days=365 * rng.randint(1, 3))),
                        "status": status,
                        "source": rng.choice(["web", "mobile", "paper", "partner"]),
                    }
                )


def make_egrul(company: Company, rng, counters: dict[str, int], tables: dict) -> None:
    founders = [
        {
            "name": row["name"],
            "inn": row["inn"],
            "share_percent": row["share_percent"],
            "type": row["founder_type"],
        }
        for row in tables["founders"]
        if row["company_id"] == company.company_id
    ]
    managers = [
        {"full_name": row["full_name"], "position": row["position"], "inn": row["inn"]}
        for row in tables["managers"]
        if row["company_id"] == company.company_id
    ]
    changes = []
    for _ in range(rng.randint(0, 4)):
        change_date = random_dt(rng, company.registration_date, C.NOW)
        changes.append(
            {
                "date": iso_date(change_date),
                "type": rng.choice(
                    ["Смена руководителя", "Изменение ОКВЭД", "Смена адреса", "Изменение состава участников", "Изменение уставного капитала"]
                ),
            }
        )
    additional = [
        profile["code"]
        for profile in rng.sample(C.OKVED_PROFILES, k=rng.randint(0, 3))
        if profile["code"] != company.okved["code"]
    ]
    tables["egrul_records"].append(
        {
            "record_id": next_id(counters, "egrul", "E", 6),
            "company_id": company.company_id,
            "inn": company.inn,
            "ogrn": company.ogrn,
            "full_name": company.legal_name,
            "short_name": company.short_name,
            "status": company.status,
            "registration_date": iso_date(company.registration_date),
            "address": company.address,
            "okved_main": company.okved["code"],
            "okved_additional": additional,
            "authorized_capital_rub": (
                0
                if company.legal_form == "ip"
                else rng.choice([10_000, 20_000, 50_000, 100_000, 500_000, 1_000_000])
            ),
            "founders_json": founders,
            "managers_json": managers,
            "changes_json": changes,
            "unreliable_record_flag": int(company.risk > 0.55 and rng.random() < 0.15),
            "mass_address_flag": int(company.risk > 0.55 and rng.random() < 0.10),
            "mass_manager_flag": int(company.risk > 0.55 and rng.random() < 0.08),
            "disqualified_manager_flag": int(rng.random() < 0.02),
            "updated_at": iso_dt(C.NOW - timedelta(days=rng.randint(0, 90))),
        }
    )


def make_sme_and_financials(
    company: Company, rng, counters: dict[str, int], tables: dict
) -> None:
    if company.status in {"active", "reorganized"}:
        tables["sme_registry"].append(
            {
                "record_id": next_id(counters, "sme", "SME", 6),
                "company_id": company.company_id,
                "category": company.segment,
                "included_at": iso_date(company.registration_date + timedelta(days=30)),
                "excluded_at": None,
                "employee_count": company.employee_count,
                "revenue_rub": company.annual_revenue_rub,
                "region": company.region["name"],
                "okved_main": company.okved["code"],
                "status": "included",
                "benefits_json": rng.sample(
                    ["Льготное кредитование", "Гарантийная поддержка", "Субсидия", "Налоговые льготы"],
                    k=rng.randint(0, 2),
                ),
            }
        )

    years = [2023, 2024, 2025]
    growth = 1.0 + rng.gauss(0.08, 0.10)
    for year in years:
        factor = growth ** (year - 2023)
        revenue = company.annual_revenue_rub * factor
        gross_margin = clamp(0.35 + 0.08 * company.quality + rng.gauss(0, 0.05), 0.05, 0.85)
        opex_ratio = clamp(0.20 + 0.03 * company.quality + rng.gauss(0, 0.03), 0.05, 0.50)
        cost = revenue * (1.0 - gross_margin)
        gross_profit = revenue - cost
        opex = revenue * opex_ratio
        ebitda = gross_profit - opex
        depreciation = revenue * rng.uniform(0.01, 0.04)
        debt = revenue * clamp(0.05 + 0.40 * company.risk + rng.gauss(0, 0.08), 0, 1.6)
        interest = debt * rng.uniform(15.0, 24.0) / 100.0
        tax_rate = 0.20 if company.tax_regime == "osn" else 0.06
        tax = max(0.0, (ebitda - depreciation - interest)) * tax_rate
        net_profit = ebitda - depreciation - interest - tax
        total_assets = revenue * clamp(rng.uniform(0.4, 1.5) * (1.0 - 0.08 * company.risk), 0.15, 2.5)
        current_assets = total_assets * rng.uniform(0.35, 0.80)
        cash = current_assets * rng.uniform(0.05, 0.25)
        receivables = current_assets * rng.uniform(0.15, 0.45)
        inventory = max(0.0, current_assets - cash - receivables)
        total_liabilities = total_assets * clamp(0.35 + 0.25 * company.risk + rng.gauss(0, 0.08), 0.15, 1.10)
        current_liabilities = total_liabilities * rng.uniform(0.45, 0.80)
        equity = total_assets - total_liabilities
        statement = {
            "statement_id": next_id(counters, "statement", "FS", 7),
            "company_id": company.company_id,
            "year": year,
            "period": "FY",
            "form": "annual",
            "revenue_rub": int_rub(revenue),
            "cost_of_sales_rub": int_rub(cost),
            "gross_profit_rub": int_rub(gross_profit),
            "operating_expenses_rub": int_rub(opex),
            "ebitda_rub": int_rub(ebitda),
            "depreciation_rub": int_rub(depreciation),
            "interest_rub": int_rub(interest),
            "tax_rub": int_rub(tax),
            "net_profit_rub": int_rub(net_profit),
            "total_assets_rub": int_rub(total_assets),
            "current_assets_rub": int_rub(current_assets),
            "cash_rub": int_rub(cash),
            "accounts_receivable_rub": int_rub(receivables),
            "inventory_rub": int_rub(inventory),
            "total_liabilities_rub": int_rub(total_liabilities),
            "current_liabilities_rub": int_rub(current_liabilities),
            "debt_rub": int_rub(debt),
            "equity_rub": int_rub(equity),
            "audit_flag": int(company.segment == "small" and rng.random() < 0.25),
            "source": rng.choice(["BFO", "1C", "client"]),
        }
        tables["financial_statements"].append(statement)

    half_year_revenue = company.annual_revenue_rub * 0.5
    tables["financial_statements"].append(
        {
            "statement_id": next_id(counters, "statement", "FS", 7),
            "company_id": company.company_id,
            "year": 2026,
            "period": "H1",
            "form": "half_year",
            "revenue_rub": int_rub(half_year_revenue),
            "cost_of_sales_rub": int_rub(half_year_revenue * 0.62),
            "gross_profit_rub": int_rub(half_year_revenue * 0.38),
            "operating_expenses_rub": int_rub(half_year_revenue * 0.22),
            "ebitda_rub": int_rub(half_year_revenue * 0.16),
            "depreciation_rub": int_rub(half_year_revenue * 0.02),
            "interest_rub": int_rub(company.total_debt_rub * 0.09),
            "tax_rub": int_rub(half_year_revenue * 0.03),
            "net_profit_rub": int_rub(company.net_profit_rub * 0.5),
            "total_assets_rub": int_rub(company.annual_revenue_rub * 0.8),
            "current_assets_rub": int_rub(company.annual_revenue_rub * 0.45),
            "cash_rub": int_rub(company.cash_rub * 0.5),
            "accounts_receivable_rub": int_rub(company.receivables_rub * 0.5),
            "inventory_rub": int_rub(company.inventory_rub * 0.5),
            "total_liabilities_rub": int_rub(company.total_debt_rub * 1.4),
            "current_liabilities_rub": int_rub(company.total_debt_rub * 0.8),
            "debt_rub": int_rub(company.total_debt_rub * 0.5),
            "equity_rub": int_rub(company.annual_revenue_rub * 0.3),
            "audit_flag": 0,
            "source": "1C",
        }
    )

    payroll = company.annual_revenue_rub * 0.18
    for year in years:
        quarter_types = C.TAX_TYPES[company.tax_regime]
        for quarter in range(1, 5):
            for tax_type in quarter_types:
                base = company.annual_revenue_rub / 4.0
                rate = 0.20
                if tax_type == "УСН":
                    rate = 0.06
                elif tax_type == "Патент":
                    rate = 0.06
                elif tax_type == "ЕСХН":
                    rate = 0.06
                elif tax_type in {"НДФЛ", "Страховые взносы"}:
                    base = payroll / 4.0
                    rate = 0.13 if tax_type == "НДФЛ" else 0.30
                elif tax_type == "Налог на прибыль":
                    base = max(0.0, company.net_profit_rub / 4.0)
                tax_amount = base * rate
                paid = tax_amount * clamp(company.discipline + rng.gauss(0, 0.05), 0.2, 1.0)
                debt_amount = max(0.0, tax_amount - paid)
                tables["tax_reports"].append(
                    {
                        "report_id": next_id(counters, "tax", "TAX", 8),
                        "company_id": company.company_id,
                        "year": year,
                        "quarter": quarter,
                        "tax_type": tax_type,
                        "taxable_base_rub": int_rub(base),
                        "tax_amount_rub": int_rub(tax_amount),
                        "paid_amount_rub": int_rub(paid),
                        "debt_amount_rub": int_rub(debt_amount),
                        "status": "paid" if debt_amount < 1 else "debt",
                        "submitted_at": iso_dt(
                            datetime(year, min(quarter * 3, 12), 28, 12, 0, tzinfo=C.NOW.tzinfo)
                            + timedelta(days=rng.randint(0, 20))
                        ),
                    }
                )
        tables["sfr_reports"].append(
            {
                "report_id": next_id(counters, "sfr", "SFR", 7),
                "company_id": company.company_id,
                "year": year,
                "insured_employees": max(1, company.employee_count + rng.randint(-2, 2)),
                "payroll_fund_rub": int_rub(payroll * (1.0 + rng.gauss(0, 0.05))),
                "contributions_rub": int_rub(payroll * 0.30),
                "debt_rub": int_rub(max(0.0, payroll * 0.30 * (1.0 - company.discipline))),
                "risk_class": rng.choice(["I", "II", "III", "IV"]),
                "benefits_json": rng.sample(["МСП", "Пониженный тариф", "Скидка по взносам"], k=rng.randint(0, 2)),
            }
        )


def make_bank(
    company: Company, rng, counters: dict[str, int], tables: dict, months: int
) -> None:
    main_bank = C.BANKS[0]
    account_count = 1 if rng.random() < 0.75 else 2
    accounts = []
    for account_index in range(account_count):
        account = {
            "account_id": next_id(counters, "account", "ACC", 6),
            "company_id": company.company_id,
            "bank_name": main_bank if account_index == 0 else rng.choice(C.BANKS[1:]),
            "account_number": make_account(rng),
            "currency": "RUB",
            "account_type": "settlement" if account_index == 0 else "special",
            "opened_at": iso_date(company.registration_date + timedelta(days=rng.randint(1, 30))),
            "status": "active" if company.status == "active" else "blocked",
            "overdraft_limit_rub": int_rub(company.monthly_revenue_rub * rng.uniform(0, 0.6)),
        }
        accounts.append(account)
        tables["bank_accounts"].append(account)
    company.bank_accounts = accounts

    main_account = accounts[0]
    opening_balance = company.monthly_revenue_rub * rng.uniform(0.10, 0.60)
    balance = opening_balance
    balances = [opening_balance]
    transactions = []

    for month_start in month_starts(months):
        season = 1.0 + 0.15 * math.sin((month_start.month / 12.0) * 2 * math.pi)
        month_revenue = company.monthly_revenue_rub * season * rng.uniform(0.75, 1.25)
        month_expenses = company.monthly_expenses_rub * rng.uniform(0.75, 1.20)
        credit_weights = {
            "revenue": 0.55,
            "acquiring": 0.20 if company.has_acquiring else 0.0,
            "loan": 0.08,
            "refund": 0.04,
            "other_income": 0.13,
        }
        debit_weights = {
            "supplier": 0.35,
            "salary": 0.18,
            "tax": 0.08,
            "rent": 0.06,
            "utilities": 0.04,
            "loan_payment": 0.10,
            "marketing": 0.05,
            "logistics": 0.04,
            "cash": 0.03,
            "other_expense": 0.07,
        }
        credit_total = sum(credit_weights.values())
        debit_total = sum(debit_weights.values())
        for category, weight in credit_weights.items():
            if weight <= 0:
                continue
            part_total = month_revenue * weight / credit_total * rng.uniform(0.85, 1.15)
            count = rng.randint(1, 4)
            shares = [rng.uniform(0.5, 1.5) for _ in range(count)]
            share_total = sum(shares)
            parts = [part_total * share / share_total for share in shares]
            parts[-1] = part_total - sum(parts[:-1])
            for part in parts:
                if part <= 0:
                    continue
                counterparty_name, purpose, channel, mcc = transaction_counterparty(
                    rng, company, category, "credit"
                )
                transactions.append(
                    {
                        "transaction_id": next_id(counters, "transaction", "TX", 8),
                        "account_id": main_account["account_id"],
                        "company_id": company.company_id,
                        "transaction_date": iso_dt(random_date_in_month(rng, month_start)),
                        "direction": "credit",
                        "amount_rub": int_rub(part),
                        "currency": "RUB",
                        "counterparty_name": counterparty_name,
                        "counterparty_inn": make_inn(rng, "llc"),
                        "purpose": purpose,
                        "category": category,
                        "channel": channel,
                        "mcc": mcc,
                    }
                )
        for category, weight in debit_weights.items():
            part_total = month_expenses * weight / debit_total * rng.uniform(0.85, 1.15)
            count = rng.randint(1, 4)
            shares = [rng.uniform(0.5, 1.5) for _ in range(count)]
            share_total = sum(shares)
            parts = [part_total * share / share_total for share in shares]
            parts[-1] = part_total - sum(parts[:-1])
            for part in parts:
                if part <= 0:
                    continue
                counterparty_name, purpose, channel, mcc = transaction_counterparty(
                    rng, company, category, "debit"
                )
                transactions.append(
                    {
                        "transaction_id": next_id(counters, "transaction", "TX", 8),
                        "account_id": main_account["account_id"],
                        "company_id": company.company_id,
                        "transaction_date": iso_dt(random_date_in_month(rng, month_start)),
                        "direction": "debit",
                        "amount_rub": int_rub(part),
                        "currency": "RUB",
                        "counterparty_name": counterparty_name,
                        "counterparty_inn": make_inn(rng, "llc"),
                        "purpose": purpose,
                        "category": category,
                        "channel": channel,
                        "mcc": mcc,
                    }
                )

    transactions.sort(key=lambda row: row["transaction_date"])
    for transaction in transactions:
        if transaction["direction"] == "credit":
            balance += transaction["amount_rub"]
        else:
            balance -= transaction["amount_rub"]
        transaction["balance_after_rub"] = int(balance)
        balances.append(balance)
        tables["bank_transactions"].append(transaction)

    main_account["balance_rub"] = int(balance)
    main_account["average_balance_rub"] = int(sum(balances) / len(balances))
    main_account["min_balance_rub"] = int(min(balances))
    main_account["max_balance_rub"] = int(max(balances))
    main_account["currency"] = "RUB"
    for extra_account in accounts[1:]:
        extra_account.update(
            {
                "balance_rub": int(company.monthly_revenue_rub * rng.uniform(0.0, 0.2)),
                "average_balance_rub": int(company.monthly_revenue_rub * rng.uniform(0.0, 0.2)),
                "min_balance_rub": 0,
                "max_balance_rub": int(company.monthly_revenue_rub * rng.uniform(0.1, 0.4)),
            }
        )

    products = []
    if company.employee_count > 2 and rng.random() < 0.85:
        products.append(
            product_row(company, rng, counters, "salary_project", main_bank)
        )
    if company.has_acquiring:
        products.append(
            product_row(company, rng, counters, "acquiring", main_bank)
        )
    if rng.random() < 0.30:
        products.append(product_row(company, rng, counters, "deposit", main_bank))
    if rng.random() < 0.45:
        products.append(product_row(company, rng, counters, "loan", main_bank))
    if rng.random() < 0.25:
        products.append(product_row(company, rng, counters, "overdraft", main_bank))
    if rng.random() < 0.10:
        products.append(product_row(company, rng, counters, "guarantee", main_bank))
    if rng.random() < 0.15:
        products.append(product_row(company, rng, counters, "leasing", main_bank))
    if (company.has_marketplace or company.has_tenders) and rng.random() < 0.10:
        products.append(product_row(company, rng, counters, "factoring", main_bank))
    company.bank_products = products
    for product in products:
        tables["bank_products"].append(product)

    tables["bank_internal_history"].append(
        {
            "history_id": next_id(counters, "internal", "BIH", 6),
            "company_id": company.company_id,
            "relationship_start": iso_date(
                company.registration_date + timedelta(days=rng.randint(1, 180))
            ),
            "segment": company.segment,
            "manager_name": make_person_name(rng)["full_name"],
            "previous_applications": rng.randint(0, 5),
            "approved_count": rng.randint(0, 3),
            "declined_count": rng.randint(0, 2),
            "defaults_count": int(company.past_due_days >= 60),
            "restructures_count": rng.randint(0, 2) if company.risk > 0.4 else 0,
            "aml_flags_json": rng.sample(
                ["none", "high_risk_geo", "cash_intensive", "rapid_turnover"],
                k=1 if company.risk < 0.5 else rng.randint(1, 2),
            ),
            "risk_flags_json": rng.sample(
                ["none", "late_tax_payments", "frequent_overdraft", "negative_balance", "related_parties"],
                k=1 if company.risk < 0.5 else rng.randint(1, 3),
            ),
            "digital_activity_score": round(clamp(0.9 - company.risk * 0.5 + rng.gauss(0, 0.1), 0.05, 0.99), 3),
            "last_activity_at": iso_dt(C.NOW - timedelta(days=rng.randint(0, 14))),
            "client_rating": rng.choice(["A", "B", "C", "D"]),
        }
    )


def transaction_counterparty(
    rng, company: Company, category: str, direction: str
) -> tuple[str, str, str, str]:
    if category == "revenue":
        return (
            rng.choice(C.COUNTERPARTY_CUSTOMERS),
            "Оплата по договору",
            rng.choice(["bank_transfer", "sbp"]),
            "",
        )
    if category == "acquiring":
        return (
            f"Эквайринг {C.BANKS[0]}",
            "Зачисление выручки по эквайрингу",
            "card",
            rng.choice(C.MCC_CODES),
        )
    if category == "loan":
        return (rng.choice(C.BANKS), "Получение кредита", "bank_transfer", "")
    if category == "refund":
        return (rng.choice(C.COUNTERPARTY_CUSTOMERS), "Возврат покупателю", "bank_transfer", "")
    if category == "other_income":
        return (rng.choice(C.SUPPLIER_NAMES), "Прочие поступления", "bank_transfer", "")
    if category == "supplier":
        return (rng.choice(C.SUPPLIER_NAMES), "Оплата поставщику", "bank_transfer", "")
    if category == "salary":
        return ("Зарплата сотрудникам", "Выплата заработной платы", "bank_transfer", "")
    if category == "tax":
        return (rng.choice(C.BANK_COUNTERPARTIES[:4]), "Уплата налогов и сборов", "bank_transfer", "")
    if category == "rent":
        return ("Арендодатель", "Арендная плата", "bank_transfer", "")
    if category == "utilities":
        return (rng.choice(C.BANK_COUNTERPARTIES[5:8]), "Коммунальные услуги", "bank_transfer", "")
    if category == "loan_payment":
        return (rng.choice(C.BANKS), "Погашение кредита и процентов", "bank_transfer", "")
    if category == "marketing":
        return ("Рекламное агентство", "Рекламные услуги", "bank_transfer", "")
    if category == "logistics":
        return ("Транспортная компания", "Логистические услуги", "bank_transfer", "")
    if category == "cash":
        return ("Снятие наличных", "Выдача наличных", "cash", "")
    return (rng.choice(C.SUPPLIER_NAMES), "Прочие расходы", "bank_transfer", "")


def product_row(
    company: Company, rng, counters: dict[str, int], product_type: str, bank_name: str
) -> dict:
    amount = 0
    outstanding = 0
    rate = 0.0
    monthly_payment = 0
    closed_at = None
    status = "active"
    days_past_due = 0
    opened_at = random_dt(rng, C.NOW - timedelta(days=1095), C.NOW - timedelta(days=30))

    if product_type in {"loan", "overdraft", "leasing", "factoring"}:
        amount = int_rub(company.annual_revenue_rub * rng.uniform(0.05, 0.50))
        outstanding = int_rub(amount * rng.uniform(0.20, 0.95))
        rate = round(rng.uniform(15.0, 28.0), 2)
        term = rng.choice([6, 12, 24, 36, 60])
        monthly_payment = int_rub(annuity_payment(outstanding, rate, term))
        days_past_due = company.past_due_days if rng.random() < company.risk * 0.5 else 0
        if days_past_due > 0:
            status = "overdue"
        elif rng.random() < 0.20:
            status = "closed"
            closed_at = iso_date(C.NOW - timedelta(days=rng.randint(1, 365)))
            outstanding = 0
            monthly_payment = 0
    elif product_type == "deposit":
        amount = int_rub(company.monthly_revenue_rub * rng.uniform(0.1, 1.5))
        outstanding = amount
        rate = round(rng.uniform(8.0, 16.0), 2)
        term = rng.choice([3, 6, 12, 24])
        monthly_payment = 0
    elif product_type == "acquiring":
        amount = int_rub(company.monthly_revenue_rub * rng.uniform(0.2, 0.9))
        outstanding = 0
        rate = round(rng.uniform(1.2, 2.5), 2)
        monthly_payment = 0
    elif product_type == "salary_project":
        amount = int_rub(company.employee_count * rng.uniform(40_000, 110_000))
        outstanding = 0
        rate = 0.0
        monthly_payment = amount
    elif product_type == "guarantee":
        amount = int_rub(company.annual_revenue_rub * rng.uniform(0.05, 0.20))
        outstanding = amount
        rate = round(rng.uniform(2.0, 6.0), 2)
        monthly_payment = 0
    else:
        amount = int_rub(company.monthly_revenue_rub)
        outstanding = amount
        rate = round(rng.uniform(5.0, 15.0), 2)
        monthly_payment = 0

    return {
        "product_id": next_id(counters, "product", "BP", 6),
        "company_id": company.company_id,
        "product_type": product_type,
        "bank_name": bank_name,
        "amount_rub": amount,
        "outstanding_rub": outstanding,
        "rate_percent": rate,
        "opened_at": iso_date(opened_at),
        "closed_at": closed_at,
        "monthly_payment_rub": monthly_payment,
        "status": status,
        "days_past_due": days_past_due,
    }


def make_bki(company: Company, rng, counters: dict[str, int], tables: dict) -> None:
    report_id = next_id(counters, "bki_report", "BKI", 6)
    loans = []
    for product in company.bank_products:
        if product["product_type"] not in {"loan", "overdraft", "leasing", "factoring"}:
            continue
        loans.append(
            {
                "loan_id": next_id(counters, "bki_loan", "BL", 7),
                "report_id": report_id,
                "company_id": company.company_id,
                "lender": product["bank_name"],
                "loan_type": product["product_type"],
                "amount_rub": product["amount_rub"],
                "outstanding_rub": product["outstanding_rub"],
                "monthly_payment_rub": product["monthly_payment_rub"],
                "opened_at": product["opened_at"],
                "closed_at": product["closed_at"],
                "status": product["status"],
                "days_past_due": product["days_past_due"],
                "currency": "RUB",
                "collateral": rng.choice(["нет", "оборудование", "недвижимость", "товары в обороте", "поручительство"]),
            }
        )
    for _ in range(rng.randint(0, 2)):
        amount = int_rub(company.annual_revenue_rub * rng.uniform(0.02, 0.20))
        outstanding = int_rub(amount * rng.uniform(0.1, 0.8))
        status = "closed" if rng.random() < 0.25 else "active"
        loans.append(
            {
                "loan_id": next_id(counters, "bki_loan", "BL", 7),
                "report_id": report_id,
                "company_id": company.company_id,
                "lender": rng.choice(C.BANKS[1:]),
                "loan_type": rng.choice(["term_loan", "credit_line", "microloan"]),
                "amount_rub": amount,
                "outstanding_rub": 0 if status == "closed" else outstanding,
                "monthly_payment_rub": 0 if status == "closed" else int_rub(outstanding / 12),
                "opened_at": iso_date(C.NOW - timedelta(days=rng.randint(180, 1500))),
                "closed_at": iso_date(C.NOW - timedelta(days=rng.randint(1, 180))) if status == "closed" else None,
                "status": status,
                "days_past_due": 0,
                "currency": "RUB",
                "collateral": rng.choice(["нет", "поручительство", "оборудование"]),
            }
        )
    for loan in loans:
        tables["credit_bureau_loans"].append(loan)

    active = [loan for loan in loans if loan["status"] != "closed"]
    credit_score = int(
        clamp(
            880
            - company.risk * 450
            - company.past_due_days * 1.2
            + company.quality * 25
            + rng.gauss(0, 20),
            300,
            900,
        )
    )
    tables["credit_bureau_reports"].append(
        {
            "report_id": report_id,
            "company_id": company.company_id,
            "bki_name": rng.choice(C.BKI_NAMES),
            "report_date": iso_date(C.NOW - timedelta(days=30)),
            "credit_score": credit_score,
            "active_loans": len(active),
            "total_outstanding_rub": sum(loan["outstanding_rub"] for loan in active),
            "monthly_payment_rub": sum(loan["monthly_payment_rub"] for loan in active),
            "max_days_past_due_12m": company.past_due_days,
            "current_past_due": company.current_past_due,
            "restructures_count": rng.randint(0, 2) if company.risk > 0.4 else 0,
            "inquiries_6m": rng.randint(0, 6),
            "applications_6m": rng.randint(0, 5),
            "fraud_flag": int(company.risk > 0.55 and rng.random() < 0.03),
        }
    )
    for quarter in range(1, 9):
        report_date = C.NOW - timedelta(days=30 + quarter * 90)
        snapshot = [
            loan
            for loan in loans
            if loan["opened_at"] <= iso_date(report_date)
            and (not loan["closed_at"] or loan["closed_at"] > iso_date(report_date))
        ]
        tables["credit_bureau_reports"].append(
            {
                "report_id": next_id(counters, "bki_report", "BKI", 6),
                "company_id": company.company_id,
                "bki_name": rng.choice(C.BKI_NAMES),
                "report_date": iso_date(report_date),
                "credit_score": int(clamp(credit_score + rng.gauss(0, 12), 300, 900)),
                "active_loans": len(snapshot),
                "total_outstanding_rub": sum(loan["outstanding_rub"] for loan in snapshot),
                "monthly_payment_rub": sum(loan["monthly_payment_rub"] for loan in snapshot),
                "max_days_past_due_12m": company.past_due_days,
                "current_past_due": company.current_past_due,
                "restructures_count": rng.randint(0, 2) if company.risk > 0.4 else 0,
                "inquiries_6m": rng.randint(0, 6),
                "applications_6m": rng.randint(0, 5),
                "fraud_flag": int(company.risk > 0.55 and rng.random() < 0.03),
            }
        )

    for _ in range(rng.randint(0, 3)):
        tables["credit_inquiries"].append(
            {
                "inquiry_id": next_id(counters, "inquiry", "INQ", 7),
                "company_id": company.company_id,
                "inquiry_date": iso_dt(C.NOW - timedelta(days=rng.randint(1, 365))),
                "lender": rng.choice(C.BANKS),
                "purpose": rng.choice(C.CREDIT_INQUIRY_PURPOSES),
                "approved": int(rng.random() < clamp(0.7 - company.risk * 0.5, 0.05, 0.9)),
                "amount_rub": int_rub(company.annual_revenue_rub * rng.uniform(0.02, 0.30)),
            }
        )


def make_legal_events(
    company: Company, rng, counters: dict[str, int], tables: dict
) -> None:
    court_count = 0
    if rng.random() < clamp(company.risk * 0.8, 0.02, 0.60):
        court_count = rng.randint(1, 3)
    for _ in range(court_count):
        role = weighted_choice(rng, ["defendant", "plaintiff"], [0.62, 0.38])
        filed_at = random_dt(rng, C.NOW - timedelta(days=730), C.NOW - timedelta(days=5))
        status = rng.choice(["В производстве", "Завершено"])
        tables["court_cases"].append(
            {
                "case_id": next_id(counters, "court", "CASE", 7),
                "company_id": company.company_id,
                "role": role,
                "court_name": f"Арбитражный суд {company.region['name']}",
                "case_number": f"А{company.region['code']}-{rng.randint(10000, 99999)}/{filed_at.year}",
                "category": rng.choice(C.COURT_CATEGORIES),
                "amount_rub": int_rub(company.annual_revenue_rub * rng.uniform(0.005, 0.20)),
                "filed_at": iso_date(filed_at),
                "status": status,
                "outcome": rng.choice(C.COURT_OUTCOMES) if status == "Завершено" else "На рассмотрении",
                "last_hearing_at": iso_date(random_dt(rng, filed_at, C.NOW)),
                "opponent_name": rng.choice(C.COUNTERPARTY_CUSTOMERS + C.SUPPLIER_NAMES),
            }
        )

    enforcement_probability = clamp(company.risk * 0.45 + 0.02, 0.02, 0.50)
    if rng.random() < enforcement_probability:
        amount = int_rub(company.annual_revenue_rub * rng.uniform(0.002, 0.08))
        paid = int_rub(amount * clamp(company.discipline + rng.gauss(0, 0.1), 0, 1))
        tables["enforcement_proceedings"].append(
            {
                "enforcement_id": next_id(counters, "enforcement", "ENF", 7),
                "company_id": company.company_id,
                "fssp_number": f"{rng.randint(10000, 99999)}/{rng.randint(2022, 2026)}",
                "amount_rub": amount,
                "opened_at": iso_date(C.NOW - timedelta(days=rng.randint(30, 900))),
                "status": "Завершено" if paid >= amount else "В работе",
                "department": f"ОСП по {company.region['city']}",
                "subject": rng.choice(C.ENFORCEMENT_SUBJECTS),
                "paid_amount_rub": paid,
            }
        )

    if company.status == "bankrupt":
        filed_at = C.NOW - timedelta(days=rng.randint(90, 900))
        tables["bankruptcy_events"].append(
            {
                "event_id": next_id(counters, "bankruptcy", "BNK", 6),
                "company_id": company.company_id,
                "event_type": "bankruptcy",
                "stage": "конкурсное производство",
                "filed_at": iso_date(filed_at),
                "status": "в процессе",
                "creditor_claims_rub": int_rub(company.total_debt_rub * rng.uniform(1.0, 2.5)),
                "manager_name": make_person_name(rng)["full_name"],
                "source": "ЕФРСБ",
            }
        )
    elif company.risk > 0.55 and rng.random() < 0.15:
        tables["bankruptcy_events"].append(
            {
                "event_id": next_id(counters, "bankruptcy", "BNK", 6),
                "company_id": company.company_id,
                "event_type": "notice",
                "stage": "заявление",
                "filed_at": iso_date(C.NOW - timedelta(days=rng.randint(1, 120))),
                "status": "на рассмотрении",
                "creditor_claims_rub": int_rub(company.total_debt_rub * rng.uniform(0.3, 0.9)),
                "manager_name": "",
                "source": "Федресурс",
            }
        )


def make_assets(
    company: Company, rng, counters: dict[str, int], tables: dict
) -> None:
    if company.has_property:
        for _ in range(rng.randint(1, 2)):
            property_type = rng.choice(C.PROPERTY_TYPES)
            area = round(rng.uniform(20, 1500), 2)
            market_value = int_rub(area * rng.uniform(30_000, 250_000))
            encumbrances = []
            if company.total_debt_rub > company.annual_revenue_rub * 0.2 and rng.random() < 0.5:
                encumbrances.append("ипотека")
            if company.risk > 0.52 and rng.random() < 0.15:
                encumbrances.append("арест")
            tables["real_estate"].append(
                {
                    "property_id": next_id(counters, "property", "PROP", 6),
                    "company_id": company.company_id,
                    "property_type": property_type,
                    "cadastral_number": make_cadastral(rng, company.region["code"]),
                    "address": company.address,
                    "area_sqm": area,
                    "cadastral_value_rub": int_rub(market_value * rng.uniform(0.6, 0.9)),
                    "market_value_rub": market_value,
                    "ownership_type": rng.choice(C.OWNERSHIP_TYPES),
                    "encumbrances_json": encumbrances,
                    "registered_at": iso_date(
                        company.registration_date + timedelta(days=rng.randint(30, 2000))
                    ),
                }
            )

    if company.has_vehicles:
        for _ in range(rng.randint(1, 3)):
            year = rng.randint(2012, 2026)
            market_value = int_rub(rng.uniform(400_000, 6_000_000))
            pledge = int(
                company.total_debt_rub > company.annual_revenue_rub * 0.15 and rng.random() < 0.4
            )
            restrictions = ["залог"] if pledge else []
            if company.risk > 0.55 and rng.random() < 0.1:
                restrictions.append("ограничение регистрационных действий")
            tables["vehicles"].append(
                {
                    "vehicle_id": next_id(counters, "vehicle", "VEH", 6),
                    "company_id": company.company_id,
                    "vehicle_type": rng.choice(C.VEHICLE_TYPES),
                    "brand": rng.choice(C.VEHICLE_BRANDS),
                    "model": rng.choice(["X5", "Transit", "Gazelle", "Actros", "FH", "Camry", "Solaris", "Vesta"]),
                    "year": year,
                    "vin": make_vin(rng),
                    "plate_number": make_plate(rng, company.region["code"]),
                    "market_value_rub": market_value,
                    "pledge_flag": pledge,
                    "restrictions_json": restrictions,
                }
            )

    if company.has_license:
        license_types = C.LICENSE_TYPES.get(company.okved["industry"], ["Прочая деятельность"])
        for license_type in rng.sample(license_types, k=min(len(license_types), rng.randint(1, 2))):
            issued_at = company.registration_date + timedelta(days=rng.randint(30, 1500))
            status = "active"
            if company.risk > 0.55 and rng.random() < 0.12:
                status = rng.choice(["suspended", "revoked"])
            tables["licenses"].append(
                {
                    "license_id": next_id(counters, "license", "LIC", 6),
                    "company_id": company.company_id,
                    "license_type": license_type,
                    "number": f"Л{rng.randint(100000, 999999)}",
                    "issued_at": iso_date(issued_at),
                    "valid_until": iso_date(issued_at + timedelta(days=365 * rng.randint(1, 5))),
                    "status": status,
                    "regulator": rng.choice(C.LICENSE_REGULATORS),
                    "activity": license_type,
                }
            )

    if company.has_tenders:
        for _ in range(rng.randint(1, 3)):
            published_at = random_dt(rng, C.NOW - timedelta(days=730), C.NOW - timedelta(days=10))
            amount = int_rub(company.annual_revenue_rub * rng.uniform(0.02, 0.30))
            status = rng.choice(["Выигран", "Проигран", "На рассмотрении"])
            result = "Контракт заключён" if status == "Выигран" else "Заявка рассмотрена"
            tables["tenders"].append(
                {
                    "tender_id": next_id(counters, "tender", "TND", 7),
                    "company_id": company.company_id,
                    "platform": rng.choice(["ЕИС", "Сбербанк-АСТ", "РТС-тендер", "ЭТП ГПБ"]),
                    "procurement_number": f"{rng.randint(1000000000000000000, 9999999999999999999)}",
                    "customer_name": rng.choice(C.COUNTERPARTY_CUSTOMERS),
                    "amount_rub": amount,
                    "status": status,
                    "published_at": iso_date(published_at),
                    "result": result,
                    "contract_amount_rub": amount if status == "Выигран" else 0,
                }
            )


def make_accounting(
    company: Company, rng, counters: dict[str, int], tables: dict, months: int
) -> None:
    for month_start in month_starts(months):
        period = period_label(month_start)
        revenue = company.monthly_revenue_rub * rng.uniform(0.8, 1.2)
        expenses = company.monthly_expenses_rub * rng.uniform(0.8, 1.2)
        pairs = [
            ("62", "90", revenue * 0.7, "ООО «Клиент»", "Реализация товаров и услуг"),
            ("51", "62", revenue * 0.6, "ООО «Клиент»", "Поступление оплаты от покупателя"),
            ("60", "51", expenses * 0.4, "ООО «Поставщик»", "Оплата поставщику"),
            ("10", "60", expenses * 0.2, "ООО «Поставщик»", "Поступление материалов"),
            ("70", "51", expenses * 0.18, "Сотрудники", "Выплата заработной платы"),
            ("68", "51", expenses * 0.08, "ИФНС", "Уплата налогов"),
            ("69", "51", expenses * 0.06, "СФР", "Уплата страховых взносов"),
            ("90", "99", revenue * 0.12, "Финансовый результат", "Закрытие месяца"),
        ]
        for _ in range(rng.randint(6, 10)):
            debit, credit, amount, counterparty, description = rng.choice(pairs)
            amount = int_rub(amount * rng.uniform(0.6, 1.3))
            if amount <= 0:
                continue
            tables["accounting_entries"].append(
                {
                    "entry_id": next_id(counters, "accounting", "AE", 8),
                    "company_id": company.company_id,
                    "period": period,
                    "debit_account": debit,
                    "credit_account": credit,
                    "amount_rub": amount,
                    "counterparty_name": counterparty,
                    "document_name": f"Документ {rng.randint(1, 999)}",
                    "description": description,
                }
            )


def make_market_data(
    company: Company, rng, counters: dict[str, int], tables: dict, months: int
) -> None:
    if company.has_marketplace:
        for month_start in month_starts(months):
            orders = max(1, int(company.monthly_revenue_rub / rng.uniform(1_500, 8_000)))
            revenue = company.monthly_revenue_rub * rng.uniform(0.05, 0.45)
            returns = int(orders * rng.uniform(0.01, 0.12))
            tables["marketplace_sales"].append(
                {
                    "sale_id": next_id(counters, "sale", "MS", 7),
                    "company_id": company.company_id,
                    "marketplace": rng.choice(C.MARKETPLACES),
                    "period": period_label(month_start),
                    "orders_count": orders,
                    "revenue_rub": int_rub(revenue),
                    "returns_count": returns,
                    "returns_amount_rub": int_rub(revenue * returns / max(orders, 1)),
                    "average_check_rub": int_rub(revenue / max(orders, 1)),
                    "rating": round(clamp(4.8 - company.risk * 1.5 + rng.gauss(0, 0.15), 2.5, 5.0), 2),
                    "commission_rub": int_rub(revenue * rng.uniform(0.10, 0.25)),
                    "penalties_rub": int_rub(revenue * rng.uniform(0, 0.02)),
                }
            )

    if company.okved["industry"] in {"Ритейл", "HoReCa", "Бытовые услуги"} or company.has_marketplace:
        for _ in range(rng.randint(20, 50)):
            receipt_date = random_dt(rng, C.NOW - timedelta(days=365), C.NOW - timedelta(days=1))
            tables["ofd_receipts"].append(
                {
                    "receipt_id": next_id(counters, "receipt", "OFD", 9),
                    "company_id": company.company_id,
                    "receipt_date": iso_dt(receipt_date),
                    "amount_rub": int_rub(rng.uniform(500, 25_000)),
                    "items_count": rng.randint(1, 8),
                    "payment_type": rng.choice(["card", "cash", "sbp"]),
                    "mcc": rng.choice(C.MCC_CODES),
                    "city": company.region["city"],
                }
            )

    if company.has_site:
        for month_start in month_starts(months):
            visits = max(10, int(company.monthly_revenue_rub / rng.uniform(20, 120)))
            conversion = clamp(rng.uniform(0.005, 0.05) + company.quality * 0.002, 0.001, 0.15)
            sources = rng.sample(C.TRAFFIC_SOURCES, k=rng.randint(2, 4))
            tables["website_metrics"].append(
                {
                    "metric_id": next_id(counters, "website", "WEB", 7),
                    "company_id": company.company_id,
                    "period": period_label(month_start),
                    "visits": visits,
                    "unique_visitors": int(visits * rng.uniform(0.6, 0.9)),
                    "conversion_rate": round(conversion, 4),
                    "average_order_value_rub": int_rub(company.monthly_revenue_rub / max(visits * conversion, 1)),
                    "ad_spend_rub": int_rub(company.monthly_revenue_rub * rng.uniform(0.01, 0.08)),
                    "traffic_sources_json": sources,
                    "domain_age_months": max(1, int((C.NOW - company.registration_date).days / 30)),
                }
            )

    for _ in range(rng.randint(1, 3)):
        source = rng.choice(C.REPUTATION_SOURCES)
        rating = round(clamp(4.7 - company.risk * 1.8 + rng.gauss(0, 0.2), 2.0, 5.0), 2)
        tables["reputation"].append(
            {
                "reputation_id": next_id(counters, "reputation", "REP", 7),
                "company_id": company.company_id,
                "source": source,
                "rating": rating,
                "reviews_count": rng.randint(0, 300),
                "negative_mentions": rng.randint(0, 20) if company.risk > 0.5 else rng.randint(0, 3),
                "last_review_at": iso_date(C.NOW - timedelta(days=rng.randint(0, 180))),
                "sentiment": "negative" if company.risk > 0.55 and rng.random() < 0.3 else "positive",
            }
        )

    for month_start in month_starts(months):
        headcount = max(1, company.employee_count + rng.randint(-2, 2))
        tables["hr_metrics"].append(
            {
                "metric_id": next_id(counters, "hr", "HR", 7),
                "company_id": company.company_id,
                "period": period_label(month_start),
                "headcount": headcount,
                "vacancies": rng.randint(0, max(1, headcount // 5)),
                "hires": rng.randint(0, max(1, headcount // 10)),
                "fires": rng.randint(0, max(1, headcount // 12)),
                "average_salary_rub": int_rub(
                    rng.uniform(35_000, 110_000) * (1.2 if company.region["code"] in {"77", "78"} else 1.0)
                ),
                "source": rng.choice(["hh.ru", "internal", "1C"]),
            }
        )

    if company.okved["industry"] in {"Ритейл", "Опт", "Логистика", "Производство"} or company.has_marketplace:
        for month_start in month_starts(months):
            shipments = rng.randint(10, 500)
            tables["logistics"].append(
                {
                    "metric_id": next_id(counters, "logistics", "LOG", 7),
                    "company_id": company.company_id,
                    "period": period_label(month_start),
                    "shipments_count": shipments,
                    "returns_count": int(shipments * rng.uniform(0.01, 0.08)),
                    "average_delivery_days": round(rng.uniform(1.5, 7.0), 2),
                    "regions_json": rng.sample([region["name"] for region in C.REGIONS], k=rng.randint(1, 5)),
                    "logistics_cost_rub": int_rub(company.monthly_expenses_rub * rng.uniform(0.02, 0.10)),
                }
            )

    for month_start in month_starts(months):
        electricity = rng.uniform(500, 20_000) * (1.0 + company.employee_count / 50)
        tables["utilities"].append(
            {
                "metric_id": next_id(counters, "utility", "UTL", 7),
                "company_id": company.company_id,
                "period": period_label(month_start),
                "electricity_kwh": round(electricity, 2),
                "water_m3": round(rng.uniform(5, 300), 2),
                "amount_rub": int_rub(rng.uniform(10_000, 250_000)),
                "debt_rub": int_rub(max(0, rng.uniform(0, 50_000) * (1.0 - company.discipline))),
            }
        )

    tables["mobile_operator"].append(
        {
            "record_id": next_id(counters, "mobile", "MOB", 7),
            "company_id": company.company_id,
            "operator": rng.choice(C.MOBILE_OPERATORS),
            "tenure_months": rng.randint(6, 180),
            "monthly_spend_rub": int_rub(rng.uniform(500, 15_000) * max(1, company.employee_count / 5)),
            "payments_on_time": int(rng.random() < company.discipline),
            "debt_rub": int_rub(max(0, rng.uniform(0, 5_000) * (1.0 - company.discipline))),
        }
    )

    if company.has_site or company.has_marketplace:
        for platform in rng.sample(C.SOCIAL_PLATFORMS, k=rng.randint(1, 2)):
            tables["social_media"].append(
                {
                    "record_id": next_id(counters, "social", "SOC", 7),
                    "company_id": company.company_id,
                    "platform": platform,
                    "followers": rng.randint(50, 100_000),
                    "posts_per_month": rng.randint(0, 30),
                    "engagement_rate": round(rng.uniform(0.005, 0.10), 4),
                    "last_post_at": iso_date(C.NOW - timedelta(days=rng.randint(0, 60))),
                }
            )

    for _ in range(rng.randint(0, 4)):
        mention_date = random_dt(rng, C.NOW - timedelta(days=730), C.NOW)
        sentiment = "negative" if company.risk > 0.55 and rng.random() < 0.3 else rng.choice(["positive", "neutral"])
        tables["news_mentions"].append(
            {
                "mention_id": next_id(counters, "news", "NEWS", 7),
                "company_id": company.company_id,
                "mention_date": iso_date(mention_date),
                "source": rng.choice(C.NEWS_SOURCES),
                "title": rng.choice(
                    [
                        "Компания расширяет производство",
                        "Новый контракт с крупным заказчиком",
                        "Изменения в руководстве",
                        "Итоги года и планы развития",
                        "Претензии контрагентов",
                    ]
                ),
                "sentiment": sentiment,
                "url": f"https://news.example.com/{company.company_id.lower()}-{rng.randint(1000, 9999)}",
            }
        )


def make_state_extras(
    company: Company, rng, counters: dict[str, int], tables: dict
) -> None:
    tax_debt = int_rub(
        company.total_debt_rub * rng.uniform(0.0, 0.06) * (1.0 - company.discipline)
    )
    risk_flags = []
    if tax_debt > 0:
        risk_flags.append("tax_debt")
    if company.discipline < 0.80:
        risk_flags.append("late_tax_payments")
    if company.risk > 0.55:
        risk_flags.append("high_risk_okved")
    if company.status != "active":
        risk_flags.append("unreliable_record")
    if company.risk > 0.55 and rng.random() < 0.50:
        risk_flags.append("vat_gap")
    tables["fns_status"].append(
        {
            "status_id": next_id(counters, "fns", "FNS", 6),
            "company_id": company.company_id,
            "tax_debt_rub": tax_debt,
            "unpaid_tax_count": rng.randint(0, 3) if tax_debt > 0 else 0,
            "blocked_accounts_count": rng.randint(0, 2) if company.risk > 0.55 else 0,
            "late_payments_12m": max(0, int((1.0 - company.discipline) * 20)),
            "special_regime": company.tax_regime,
            "risk_level": "high" if len(risk_flags) >= 3 else ("medium" if risk_flags else "low"),
            "risk_flags_json": risk_flags,
            "updated_at": iso_dt(C.NOW - timedelta(days=rng.randint(0, 30))),
        }
    )

    quarter_starts = month_starts(12)[::3]
    for month_start in quarter_starts:
        for indicator in C.ROSSTAT_INDICATORS:
            if indicator["unit"] == "rub":
                value = rng.uniform(45_000, 120_000)
            else:
                value = clamp(100.0 + rng.gauss(0, 8.0), 70.0, 135.0)
            tables["rosstat_indicators"].append(
                {
                    "indicator_id": next_id(counters, "rosstat", "ROS", 7),
                    "company_id": company.company_id,
                    "period": period_label(month_start),
                    "indicator": indicator["indicator"],
                    "value": round(value, 2),
                    "unit": indicator["unit"],
                    "source": "Росстат",
                }
            )

    if rng.random() < 0.15:
        registered_at = C.NOW - timedelta(days=rng.randint(180, 3000))
        ip_type = weighted_choice(rng, C.IP_TYPES, [0.40, 0.35, 0.25])
        status = weighted_choice(rng, C.IP_STATUSES, [0.75, 0.10, 0.10, 0.05])
        titles = {
            "patent": f"Способ/устройство — {company.okved['name'].lower()}",
            "trademark": company.short_name,
            "software": f"Программа для {company.okved['name'].lower()}",
        }
        tables["intellectual_property"].append(
            {
                "ip_id": next_id(counters, "ip", "IP", 6),
                "company_id": company.company_id,
                "ip_type": ip_type,
                "number": f"{rng.randint(1000000, 9999999)}",
                "title": titles[ip_type],
                "status": status,
                "registered_at": iso_date(registered_at),
                "valid_until": iso_date(registered_at + timedelta(days=365 * rng.randint(3, 10))),
            }
        )

    if company.has_export or rng.random() < 0.05:
        for _ in range(rng.randint(1, 3)):
            currency = rng.choice(list(C.CURRENCY_RATES.keys()))
            value_rub = int_rub(company.annual_revenue_rub * rng.uniform(0.01, 0.12))
            tables["customs_declarations"].append(
                {
                    "declaration_id": next_id(counters, "customs", "CD", 7),
                    "company_id": company.company_id,
                    "declaration_number": f"10{rng.randint(10000000, 99999999)}/{rng.randint(100000, 999999)}",
                    "declaration_date": iso_date(C.NOW - timedelta(days=rng.randint(10, 700))),
                    "direction": weighted_choice(rng, ["export", "import"], [0.70, 0.30]),
                    "country": rng.choice(C.CUSTOMS_COUNTRIES),
                    "hs_code": rng.choice(C.CUSTOMS_HS_CODES),
                    "goods_json": [rng.choice(C.CUSTOMS_GOODS)],
                    "value_rub": value_rub,
                    "currency": currency,
                    "customs_payments_rub": int_rub(value_rub * rng.uniform(0.01, 0.06)),
                }
            )

    if rng.random() < 0.30:
        for _ in range(rng.randint(1, 3)):
            requested_at = C.NOW - timedelta(days=rng.randint(10, 400))
            status = weighted_choice(rng, ["completed", "in_progress", "rejected"], [0.70, 0.20, 0.10])
            tables["gosuslugi_events"].append(
                {
                    "event_id": next_id(counters, "gosuslugi", "GU", 7),
                    "company_id": company.company_id,
                    "user_id": rng.choice(company.users).user_id if company.users else None,
                    "service": rng.choice(C.GOSUSLUGI_SERVICES),
                    "status": status,
                    "requested_at": iso_dt(requested_at),
                    "completed_at": iso_dt(requested_at + timedelta(days=rng.randint(1, 30)))
                    if status == "completed"
                    else None,
                    "payload_json": {
                        "application_number": f"{rng.randint(100000000, 999999999)}",
                        "source": "ЕПГУ",
                    },
                }
            )

    if rng.random() < 0.10:
        tables["rating_agency_ratings"].append(
            {
                "rating_id": next_id(counters, "rating", "RAT", 6),
                "company_id": company.company_id,
                "agency": rng.choice(C.RATING_AGENCIES),
                "rating": weighted_choice(rng, C.RATING_VALUES, [0.15, 0.20, 0.20, 0.15, 0.15, 0.10, 0.05]),
                "outlook": rng.choice(C.RATING_OUTLOOKS),
                "assigned_at": iso_date(C.NOW - timedelta(days=rng.randint(30, 730))),
                "status": "active",
            }
        )

    for _ in range(rng.randint(1, 3)):
        risk_score = round(clamp(company.risk + rng.gauss(0, 0.08), 0.01, 0.99), 3)
        flags = rng.sample(
            C.COUNTERPARTY_RISK_FLAGS,
            k=min(len(C.COUNTERPARTY_RISK_FLAGS), rng.randint(0, 3) + (2 if risk_score > 0.6 else 0)),
        )
        tables["counterparty_checks"].append(
            {
                "check_id": next_id(counters, "counterparty", "CC", 7),
                "company_id": company.company_id,
                "service": rng.choice(C.CHECK_SERVICES),
                "checked_at": iso_dt(C.NOW - timedelta(days=rng.randint(0, 120))),
                "risk_score": risk_score,
                "risk_level": "high" if risk_score > 0.55 else ("medium" if risk_score > 0.40 else "low"),
                "risk_flags_json": flags,
                "status": "completed",
            }
        )

    history_events = ["registration", "address_change", "director_change", "okved_change", "capital_change"]
    for event_type in rng.sample(history_events, k=rng.randint(1, 4)):
        event_date = random_dt(rng, company.registration_date, C.NOW - timedelta(days=5))
        descriptions = {
            "registration": "Регистрация компании",
            "address_change": "Изменение юридического адреса",
            "director_change": "Смена руководителя",
            "okved_change": "Изменение основного ОКВЭД",
            "capital_change": "Изменение уставного капитала",
        }
        tables["business_history"].append(
            {
                "history_id": next_id(counters, "history", "BH", 7),
                "company_id": company.company_id,
                "event_date": iso_date(event_date),
                "event_type": event_type,
                "description": descriptions[event_type],
                "source": "ЕГРЮЛ",
                "payload_json": {"synthetic": True, "event_type": event_type},
            }
        )


def make_digital_extras(
    company: Company, rng, counters: dict[str, int], tables: dict, months: int
) -> None:
    if company.has_site:
        domain = company.website.replace("https://", "").replace("http://", "").strip("/")
        created_at = company.registration_date + timedelta(days=rng.randint(0, 120))
        tables["domain_whois"].append(
            {
                "record_id": next_id(counters, "whois", "WHOIS", 6),
                "company_id": company.company_id,
                "domain": domain,
                "registrar": rng.choice(["REG.RU", "Timeweb", "Beget", "RU-CENTER"]),
                "created_at": iso_date(created_at),
                "expires_at": iso_date(C.NOW + timedelta(days=rng.randint(30, 700))),
                "status": "active",
                "privacy_flag": int(rng.random() < 0.60),
            }
        )

    for source in rng.sample(C.REPUTATION_SOURCES, k=rng.randint(1, 2)):
        tables["geo_metrics"].append(
            {
                "metric_id": next_id(counters, "geo", "GEO", 7),
                "company_id": company.company_id,
                "source": source,
                "rating": round(clamp(4.7 - company.risk * 1.7 + rng.gauss(0, 0.2), 2.0, 5.0), 2),
                "reviews_count": rng.randint(0, 400),
                "checkins_month": rng.randint(0, 1500),
                "photos_count": rng.randint(0, 100),
                "last_updated_at": iso_dt(C.NOW - timedelta(days=rng.randint(0, 30))),
            }
        )

    if rng.random() < 0.70:
        connected = int(rng.random() < 0.85)
        tables["accounting_systems"].append(
            {
                "connection_id": next_id(counters, "accounting_system", "AS", 6),
                "company_id": company.company_id,
                "system": rng.choice(C.ACCOUNTING_SYSTEMS),
                "connected": connected,
                "last_sync_at": iso_dt(C.NOW - timedelta(hours=rng.randint(0, 72)))
                if connected
                else None,
                "data_quality": round(clamp(0.9 - company.risk * 0.3 + rng.gauss(0, 0.05), 0.2, 0.99), 3),
                "status": "active" if connected else "disconnected",
            }
        )

    if company.has_acquiring or rng.random() < 0.35:
        tables["payment_services"].append(
            {
                "service_id": next_id(counters, "payment_service", "PS", 6),
                "company_id": company.company_id,
                "provider": rng.choice(C.PAYMENT_PROVIDERS),
                "connected": 1,
                "monthly_turnover_rub": int_rub(company.monthly_revenue_rub * rng.uniform(0.10, 0.60)),
                "average_ticket_rub": int_rub(rng.uniform(800, 12_000)),
                "refund_rate": round(rng.uniform(0.0, 0.08), 4),
                "connected_at": iso_date(company.registration_date + timedelta(days=rng.randint(10, 500))),
                "status": "active",
            }
        )

    for month_start in month_starts(months):
        season = 1.0 + 0.10 * math.sin((month_start.month / 12.0) * 2 * math.pi)
        revenue = company.monthly_revenue_rub * season * rng.uniform(0.85, 1.15)
        expenses = company.monthly_expenses_rub * rng.uniform(0.85, 1.15)
        tables["management_reports"].append(
            {
                "report_id": next_id(counters, "management", "MR", 7),
                "company_id": company.company_id,
                "period": period_label(month_start),
                "revenue_rub": int_rub(revenue),
                "expenses_rub": int_rub(expenses),
                "profit_rub": int_rub(revenue - expenses),
                "cash_rub": int_rub(max(0.0, company.cash_rub * rng.uniform(0.5, 1.5))),
                "accounts_receivable_rub": int_rub(max(0.0, company.receivables_rub * rng.uniform(0.6, 1.4))),
                "accounts_payable_rub": int_rub(max(0.0, company.total_debt_rub * rng.uniform(0.10, 0.40))),
                "source": rng.choice(["1C", "client", "management"]),
            }
        )


def make_alternative_data(
    company: Company, rng, counters: dict[str, int], tables: dict, months: int
) -> None:
    if rng.random() < 0.40:
        insurance_types = rng.sample(C.INSURANCE_TYPES, k=rng.randint(1, 2))
        for insurance_type in insurance_types:
            insured_amount = int_rub(company.annual_revenue_rub * rng.uniform(0.05, 0.50))
            valid_from = C.NOW - timedelta(days=rng.randint(0, 300))
            tables["insurance_policies"].append(
                {
                    "policy_id": next_id(counters, "insurance", "INS", 7),
                    "company_id": company.company_id,
                    "insurance_type": insurance_type,
                    "insurer": rng.choice(C.INSURERS),
                    "premium_rub": int_rub(insured_amount * rng.uniform(0.005, 0.04)),
                    "insured_amount_rub": insured_amount,
                    "valid_from": iso_date(valid_from),
                    "valid_until": iso_date(valid_from + timedelta(days=365)),
                    "status": "active" if rng.random() < 0.85 else "expired",
                    "coverage_json": rng.sample(
                        ["имущество", "ответственность", "персонал", "перерывы в деятельности"],
                        k=rng.randint(1, 3),
                    ),
                }
            )

    if company.has_vehicles and rng.random() < 0.70:
        for _ in range(rng.randint(1, 2)):
            tables["fuel_cards"].append(
                {
                    "card_id": next_id(counters, "fuel", "FC", 6),
                    "company_id": company.company_id,
                    "provider": rng.choice(C.FUEL_PROVIDERS),
                    "cards_count": rng.randint(1, max(1, company.employee_count // 3)),
                    "monthly_spend_rub": int_rub(rng.uniform(15_000, 400_000)),
                    "last_transaction_at": iso_dt(C.NOW - timedelta(days=rng.randint(0, 20))),
                    "status": "active",
                }
            )

    vehicles = [row for row in tables["vehicles"] if row["company_id"] == company.company_id]
    for vehicle in vehicles:
        if rng.random() >= 0.50:
            continue
        provider = rng.choice(C.TELEMATICS_PROVIDERS)
        for month_start in month_starts(min(months, 3)):
            tables["telematics"].append(
                {
                    "record_id": next_id(counters, "telematics", "TLM", 7),
                    "company_id": company.company_id,
                    "vehicle_id": vehicle["vehicle_id"],
                    "provider": provider,
                    "period": period_label(month_start),
                    "mileage_km": round(rng.uniform(500, 12_000), 2),
                    "idle_hours": round(rng.uniform(5, 120), 2),
                    "fuel_consumption_l": round(rng.uniform(50, 1_800), 2),
                    "harsh_events": rng.randint(0, 25),
                    "last_signal_at": iso_dt(C.NOW - timedelta(hours=rng.randint(0, 48))),
                }
            )

    if rng.random() < (0.30 if company.okved["industry"] in {"Производство", "Сельское хозяйство", "Логистика"} else 0.10):
        for sensor in rng.sample(C.IOT_SENSORS, k=rng.randint(1, 3)):
            tables["iot_sensors"].append(
                {
                    "record_id": next_id(counters, "iot", "IOT", 7),
                    "company_id": company.company_id,
                    "sensor_type": sensor["sensor_type"],
                    "metric_name": sensor["metric_name"],
                    "value": round(rng.uniform(1.0, 5_000.0), 3),
                    "unit": sensor["unit"],
                    "recorded_at": iso_dt(C.NOW - timedelta(hours=rng.randint(0, 24))),
                    "status": "online",
                }
            )

    if company.okved["industry"] in {"Ритейл", "Опт", "Производство", "HoReCa"}:
        for month_start in month_starts(months):
            tables["warehouse_stock"].append(
                {
                    "record_id": next_id(counters, "warehouse", "WH", 7),
                    "company_id": company.company_id,
                    "period": period_label(month_start),
                    "sku_count": rng.randint(10, 2_000),
                    "stock_value_rub": int_rub(max(0.0, company.inventory_rub * rng.uniform(0.6, 1.4))),
                    "turnover_days": round(rng.uniform(7, 120), 1),
                    "slow_moving_share": round(rng.uniform(0.0, 0.35), 4),
                    "stockout_rate": round(rng.uniform(0.0, 0.12), 4),
                }
            )

    if rng.random() < 0.05:
        tables["franchise_contracts"].append(
            {
                "contract_id": next_id(counters, "franchise", "FR", 6),
                "company_id": company.company_id,
                "franchisor": rng.choice(C.FRANCHISORS),
                "contract_date": iso_date(company.registration_date + timedelta(days=rng.randint(10, 900))),
                "outlets_count": rng.randint(1, 5),
                "royalty_percent": round(rng.uniform(2.0, 12.0), 2),
                "status": "active",
                "terms_json": {"marketing_fee_percent": round(rng.uniform(0.5, 3.0), 2)},
            }
        )

    if rng.random() < 0.12:
        for _ in range(rng.randint(1, 2)):
            tables["grants_subsidies"].append(
                {
                    "grant_id": next_id(counters, "grant", "GR", 6),
                    "company_id": company.company_id,
                    "program": rng.choice(C.GRANT_PROGRAMS),
                    "amount_rub": int_rub(rng.uniform(100_000, 10_000_000)),
                    "received_at": iso_date(C.NOW - timedelta(days=rng.randint(30, 900))),
                    "status": weighted_choice(rng, ["received", "approved", "rejected"], [0.65, 0.25, 0.10]),
                    "purpose": rng.choice(C.PURPOSES),
                }
            )

    if rng.random() < 0.20:
        for standard in rng.sample(C.CERTIFICATION_STANDARDS, k=rng.randint(1, 2)):
            issued_at = C.NOW - timedelta(days=rng.randint(30, 1500))
            tables["certifications"].append(
                {
                    "certification_id": next_id(counters, "certification", "CERT", 6),
                    "company_id": company.company_id,
                    "standard": standard,
                    "certificate_number": f"RU.{rng.randint(100000, 999999)}",
                    "issued_at": iso_date(issued_at),
                    "valid_until": iso_date(issued_at + timedelta(days=365 * 3)),
                    "status": "active" if rng.random() < 0.85 else "expired",
                    "certification_body": rng.choice(C.CERTIFICATION_BODIES),
                }
            )

    if rng.random() < 0.15:
        tables["industry_memberships"].append(
            {
                "membership_id": next_id(counters, "membership", "MEM", 6),
                "company_id": company.company_id,
                "association": rng.choice(C.ASSOCIATIONS),
                "member_since": iso_date(company.registration_date + timedelta(days=rng.randint(30, 1000))),
                "status": "active",
                "role": rng.choice(["member", "committee", "board"]),
            }
        )

    if company.okved["industry"] in {"Ритейл", "Опт", "Производство"} and rng.random() < 0.20:
        for network in rng.sample(C.TRADE_NETWORKS, k=rng.randint(1, 2)):
            tables["trade_networks"].append(
                {
                    "contract_id": next_id(counters, "trade_network", "TN", 6),
                    "company_id": company.company_id,
                    "network": network,
                    "contract_date": iso_date(company.registration_date + timedelta(days=rng.randint(30, 1200))),
                    "revenue_share_percent": round(rng.uniform(2.0, 40.0), 2),
                    "status": "active",
                    "payment_delay_days": rng.choice([0, 14, 30, 45, 60, 90]),
                }
            )

    for user in company.users:
        if rng.random() >= 0.08:
            continue
        checked_at = C.NOW - timedelta(days=rng.randint(1, 180))
        tables["biometric_checks"].append(
            {
                "check_id": next_id(counters, "biometric", "BIO", 7),
                "user_id": user.user_id,
                "company_id": company.company_id,
                "check_type": rng.choice(C.BIOMETRIC_TYPES),
                "provider": rng.choice(C.BIOMETRIC_PROVIDERS),
                "status": weighted_choice(rng, ["passed", "failed", "pending"], [0.90, 0.06, 0.04]),
                "checked_at": iso_dt(checked_at),
                "liveness_score": round(rng.uniform(0.75, 0.999), 4),
            }
        )


def make_currency_operations(
    company: Company, rng, counters: dict[str, int], tables: dict
) -> None:
    if not company.bank_accounts:
        return
    if not (company.has_export or rng.random() < 0.15):
        return
    account = company.bank_accounts[0]
    for _ in range(rng.randint(2, 8)):
        currency = rng.choice(list(C.CURRENCY_RATES.keys()))
        rate = round(C.CURRENCY_RATES[currency] * rng.uniform(0.95, 1.05), 4)
        amount_original = round(company.monthly_revenue_rub / rate * rng.uniform(0.01, 0.30), 2)
        tables["currency_operations"].append(
            {
                "operation_id": next_id(counters, "currency", "FX", 7),
                "account_id": account["account_id"],
                "company_id": company.company_id,
                "operation_date": iso_dt(random_dt(rng, C.NOW - timedelta(days=365), C.NOW - timedelta(days=1))),
                "direction": weighted_choice(rng, ["credit", "debit"], [0.55, 0.45]),
                "currency": currency,
                "amount_original": amount_original,
                "rate": rate,
                "amount_rub": int_rub(amount_original * rate),
                "purpose": rng.choice(
                    ["Оплата по внешнеторговому контракту", "Экспортная выручка", "Импортная поставка", "Возврат средств"]
                ),
                "counterparty_name": rng.choice(C.COUNTERPARTY_CUSTOMERS + C.SUPPLIER_NAMES),
            }
        )


def application_reasons(company: Company, pd_value: float, requested_amount: float) -> list[dict]:
    reasons = []
    if company.current_past_due:
        reasons.append(
            {
                "code": "CURRENT_PAST_DUE",
                "description": "Есть текущая просрочка",
                "feature": "has_current_past_due",
                "impact": "negative",
                "contribution": 2.5,
            }
        )
    if company.past_due_days >= 30:
        reasons.append(
            {
                "code": "PAST_DUE_HISTORY",
                "description": "Просрочки за последний год",
                "feature": "max_days_past_due_12m",
                "impact": "negative",
                "contribution": 1.5,
            }
        )
    debt_to_revenue = company.total_debt_rub / max(company.annual_revenue_rub, 1)
    if debt_to_revenue > 0.4:
        reasons.append(
            {
                "code": "DEBT_BURDEN",
                "description": "Высокая долговая нагрузка",
                "feature": "debt_to_revenue",
                "impact": "negative",
                "contribution": 1.2,
            }
        )
    else:
        reasons.append(
            {
                "code": "DEBT_BURDEN",
                "description": "Низкая долговая нагрузка",
                "feature": "debt_to_revenue",
                "impact": "positive",
                "contribution": -0.8,
            }
        )
    if pd_value > 0.20:
        reasons.append(
            {
                "code": "RISK_SCORE",
                "description": "Повышенный уровень риска",
                "feature": "risk_score",
                "impact": "negative",
                "contribution": 1.0,
            }
        )
    if company.net_profit_rub / max(company.annual_revenue_rub, 1) < 0.03:
        reasons.append(
            {
                "code": "PROFITABILITY",
                "description": "Низкая рентабельность",
                "feature": "profitability",
                "impact": "negative",
                "contribution": 0.7,
            }
        )
    if company.registration_date > C.NOW - timedelta(days=365 * 2):
        reasons.append(
            {
                "code": "BUSINESS_AGE",
                "description": "Молодой бизнес без длительной истории",
                "feature": "company_age_months",
                "impact": "negative",
                "contribution": 0.6,
            }
        )
    if requested_amount / max(company.annual_revenue_rub, 1) > 0.5:
        reasons.append(
            {
                "code": "LOAN_TO_REVENUE",
                "description": "Запрос велик относительно выручки",
                "feature": "requested_to_annual_revenue",
                "impact": "negative",
                "contribution": 0.5,
            }
        )
    if company.quality > 0.5:
        reasons.append(
            {
                "code": "FINANCIAL_QUALITY",
                "description": "Устойчивые финансовые показатели",
                "feature": "financial_quality",
                "impact": "positive",
                "contribution": -0.6,
            }
        )
    return reasons[:5]


def make_applications(
    company: Company, rng, counters: dict[str, int], tables: dict, months: int
) -> None:
    if not company.users:
        return
    count = rng.choices([1, 2, 3], weights=[0.45, 0.40, 0.15], k=1)[0]
    monthly_debt_payment = sum(
        product["monthly_payment_rub"]
        for product in company.bank_products
        if product["product_type"] in {"loan", "overdraft", "leasing", "factoring"}
    )
    for _ in range(count):
        app_id = next_id(counters, "application", "A", 7)
        user = rng.choice(company.users)
        product_type = weighted_choice(
            rng, C.PRODUCTS, [0.30, 0.35, 0.10, 0.15, 0.10]
        )
        requested_amount = int_rub(
            company.annual_revenue_rub
            * rng.uniform(0.02, 0.60)
            * (1.2 if product_type == "term_loan" else 1.0)
        )
        requested_amount = max(100_000, min(requested_amount, 50_000_000))
        term_months = rng.choice([6, 12, 24, 36, 60])
        purpose = rng.choice(C.PURPOSES)
        application_start = max(
            C.NOW - timedelta(days=months * 30),
            company.registration_date + timedelta(days=90),
        )
        submitted_at = random_dt(
            rng,
            min(application_start, C.NOW - timedelta(days=32)),
            C.NOW - timedelta(days=2),
        )
        is_draft = rng.random() < 0.10

        pd_value = clamp(
            0.01
            + company.risk * 0.28
            + rng.gauss(0.0, 0.07)
            + (0.15 if company.current_past_due else 0.0),
            0.001,
            0.97,
        )
        if rng.random() < 0.12:
            pd_value = clamp(pd_value + rng.uniform(0.10, 0.30), 0.001, 0.97)
        score = max(0, min(1000, round((1.0 - pd_value) * 1000)))
        if pd_value < 0.02:
            grade = "A"
        elif pd_value < 0.05:
            grade = "B"
        elif pd_value < 0.10:
            grade = "C"
        elif pd_value < 0.20:
            grade = "D"
        else:
            grade = "E"
        reasons = application_reasons(company, pd_value, requested_amount)

        debt_service_ratio = monthly_debt_payment / max(company.monthly_revenue_rub, 1)
        loan_to_revenue = requested_amount / max(company.annual_revenue_rub, 1)
        policy_decision = "approve"
        policy_reasons = []
        conditions = []
        if company.current_past_due:
            policy_decision = "decline"
            policy_reasons = ["CURRENT_PAST_DUE"]
        elif company.past_due_days >= 60:
            policy_decision = "decline"
            policy_reasons = ["SEVERE_PAST_DUE_HISTORY"]
        elif pd_value >= 0.35:
            policy_decision = "decline"
            policy_reasons = ["HIGH_RISK_SCORE"]
        elif pd_value >= 0.20:
            policy_decision = "manual_review"
            policy_reasons = ["RISK_IN_GREY_ZONE"]
        elif debt_service_ratio > 0.55:
            policy_decision = "manual_review"
            policy_reasons = ["HIGH_DEBT_SERVICE_RATIO"]
        elif loan_to_revenue > 0.60 and requested_amount > 3_000_000:
            policy_decision = "approve_with_conditions"
            policy_reasons = ["LOAN_TO_REVENUE_REDUCTION"]
            conditions = [
                {
                    "code": "REDUCE_AMOUNT",
                    "description": "Снизить сумму финансирования относительно запрошенной",
                    "recommended_amount_rub": min(
                        requested_amount, int_rub(company.annual_revenue_rub * 0.5)
                    ),
                }
            ]

        if is_draft:
            status = "draft"
            decision = "pending"
            decision_at = None
            policy_decision = "pending"
            policy_reasons = []
            conditions = []
        elif rng.random() < 0.06:
            status = "scoring"
            decision = "pending"
            decision_at = None
            policy_decision = "pending"
            policy_reasons = []
            conditions = []
        elif policy_decision == "decline":
            status = "rejected"
            decision = "decline"
            decision_at = submitted_at + timedelta(hours=rng.randint(2, 72))
        elif policy_decision == "manual_review":
            status = "manual_review"
            decision = "manual_review"
            decision_at = submitted_at + timedelta(hours=rng.randint(2, 72))
        else:
            decision = policy_decision
            decision_at = submitted_at + timedelta(hours=rng.randint(2, 72))
            status = weighted_choice(
                rng,
                ["issued", "offer_sent", "approved", "offer_accepted"],
                [0.55, 0.20, 0.15, 0.10],
            )

        rejection_reason = ""
        if decision == "decline":
            rejection_reason = policy_reasons[0] if policy_reasons else "HIGH_RISK_SCORE"

        tables["applications"].append(
            {
                "application_id": app_id,
                "company_id": company.company_id,
                "user_id": user.user_id,
                "product_type": product_type,
                "requested_amount_rub": requested_amount,
                "term_months": term_months,
                "purpose": purpose,
                "submitted_at": iso_dt(submitted_at),
                "status": status,
                "decision": decision,
                "decision_at": iso_dt(decision_at) if decision_at else None,
                "rejection_reason": rejection_reason,
            }
        )

        if (
            status in {"approved", "offer_sent", "offer_accepted", "issued"}
            and submitted_at <= C.NOW - timedelta(days=32)
        ):
            bureau_score = (
                880.0
                - company.risk * 450.0
                - company.past_due_days * 1.2
                + company.quality * 25.0
            )
            score_risk = clamp((780.0 - bureau_score) / 250.0, 0.0, 1.0)
            default_probability = clamp(
                0.02 + 0.45 * score_risk,
                0.01,
                0.45,
            )
            if rng.random() < default_probability:
                event_at = submitted_at + timedelta(
                    days=rng.randint(1, 30), hours=rng.randint(0, 23)
                )
                days_past_due = rng.randint(30, 180)
                tables["loan_default_events"].append(
                    {
                        "event_id": next_id(counters, "default_event", "DFE", 7),
                        "application_id": app_id,
                        "company_id": company.company_id,
                        "event_type": "default",
                        "severity": "severe" if days_past_due >= 90 else "moderate",
                        "event_at": iso_dt(event_at),
                        "days_past_due": days_past_due,
                        "amount_rub": int_rub(
                            requested_amount * rng.uniform(0.25, 1.0)
                        ),
                        "source": "loan_servicing",
                    }
                )

        obligations = []
        if company.total_debt_rub > 0:
            obligations.append({"type": "credit", "amount_rub": int_rub(company.total_debt_rub)})
        if monthly_debt_payment > 0:
            obligations.append({"type": "monthly_payments", "amount_rub": int_rub(monthly_debt_payment)})
        tables["self_assessments"].append(
            {
                "assessment_id": next_id(counters, "assessment", "SA", 8),
                "application_id": app_id,
                "company_id": company.company_id,
                "declared_annual_revenue_rub": int_rub(company.annual_revenue_rub * rng.uniform(0.85, 1.15)),
                "declared_monthly_revenue_rub": int_rub(company.monthly_revenue_rub * rng.uniform(0.85, 1.15)),
                "declared_monthly_expenses_rub": int_rub(company.monthly_expenses_rub * rng.uniform(0.85, 1.15)),
                "declared_total_debt_rub": int_rub(company.total_debt_rub * rng.uniform(0.80, 1.20)),
                "declared_monthly_debt_payment_rub": int_rub(monthly_debt_payment * rng.uniform(0.80, 1.20)),
                "declared_employees": max(1, company.employee_count + rng.randint(-2, 2)),
                "declared_net_profit_rub": int_rub(company.net_profit_rub * rng.uniform(0.80, 1.20)),
                "obligations_json": obligations,
                "source": "client",
                "created_at": iso_dt(submitted_at - timedelta(hours=rng.randint(1, 48))),
            }
        )
        if rng.random() < 0.35:
            collateral_type = rng.choice(C.COLLATERAL_TYPES)
            tables["collateral_offers"].append(
                {
                    "collateral_id": next_id(counters, "collateral", "COL", 7),
                    "application_id": app_id,
                    "company_id": company.company_id,
                    "collateral_type": collateral_type,
                    "description": f"{collateral_type} — {company.short_name}",
                    "market_value_rub": int_rub(company.annual_revenue_rub * rng.uniform(0.05, 0.50)),
                    "ownership_type": rng.choice(C.COLLATERAL_OWNERSHIP),
                    "encumbrance": rng.choice(["нет", "залог", "арест"]),
                    "insurance_flag": int(rng.random() < 0.55),
                    "accepted_flag": int(pd_value < 0.25 and rng.random() < 0.75),
                }
            )

        events = [("created", "created", submitted_at - timedelta(hours=rng.randint(1, 24)))]
        if not is_draft:
            events.append(("submitted", "submitted", submitted_at))
            events.append(("data_check", "completed", submitted_at + timedelta(minutes=rng.randint(5, 60))))
            events.append(("scoring", "completed", submitted_at + timedelta(hours=rng.randint(1, 4))))
        if decision != "pending":
            events.append(("policy", "completed", decision_at - timedelta(hours=1)))
            if decision == "decline":
                events.append(("decision", "rejected", decision_at))
            elif decision == "manual_review":
                events.append(("manual_review", "in_progress", decision_at))
            else:
                events.append(("offer", "prepared", decision_at))
        if status in {"offer_sent", "offer_accepted", "issued"}:
            events.append(("offer", "sent", decision_at + timedelta(hours=2)))
        if status in {"offer_accepted", "issued"}:
            events.append(("signing", "completed", decision_at + timedelta(days=1)))
        if status == "issued":
            events.append(("issuance", "completed", decision_at + timedelta(days=2)))

        for stage, event_status, event_time in events:
            event_id = next_id(counters, "event", "EV", 9)
            comment = f"Этап {stage}: {event_status}"
            tables["application_events"].append(
                {
                    "event_id": event_id,
                    "application_id": app_id,
                    "stage": stage,
                    "status": event_status,
                    "actor": "system" if stage in {"scoring", "policy", "data_check"} else "user",
                    "created_at": iso_dt(event_time),
                    "comment": comment,
                }
            )
            tables["audit_log"].append(
                {
                    "log_id": next_id(counters, "audit", "LOG", 9),
                    "company_id": company.company_id,
                    "application_id": app_id,
                    "event_type": f"application.{stage}.{event_status}",
                    "actor": "system" if stage in {"scoring", "policy", "data_check"} else "user",
                    "payload_json": {"stage": stage, "status": event_status},
                    "created_at": iso_dt(event_time),
                }
            )

        if not is_draft:
            tables["scoring_results"].append(
                {
                    "scoring_id": next_id(counters, "scoring", "SC", 8),
                    "application_id": app_id,
                    "model_version": C.MODEL_VERSION,
                    "score": score,
                    "pd": round(pd_value, 6),
                    "risk_grade": grade,
                    "reason_codes_json": reasons,
                    "created_at": iso_dt(submitted_at + timedelta(hours=2)),
                }
            )

        if decision != "pending":
            tables["policy_decisions"].append(
                {
                    "decision_id": next_id(counters, "decision", "PD", 8),
                    "application_id": app_id,
                    "decision": policy_decision,
                    "reason_codes_json": policy_reasons,
                    "conditions_json": conditions,
                    "created_at": iso_dt(decision_at),
                }
            )

        if status in {"approved", "offer_sent", "offer_accepted", "issued"}:
            approved_amount = requested_amount
            if conditions:
                approved_amount = conditions[0]["recommended_amount_rub"]
            rate = round(clamp(18.0 + company.risk * 15.0 + rng.gauss(0, 2.0), 14.0, 35.0), 2)
            monthly_payment = int_rub(annuity_payment(approved_amount, rate, term_months))
            offer_status = "accepted" if status in {"offer_accepted", "issued"} else "sent"
            offer_id = next_id(counters, "offer", "OFF", 7)
            tables["offers"].append(
                {
                    "offer_id": offer_id,
                    "application_id": app_id,
                    "approved_amount_rub": approved_amount,
                    "rate_percent": rate,
                    "term_months": term_months,
                    "monthly_payment_rub": monthly_payment,
                    "conditions_json": conditions,
                    "valid_until": iso_date(decision_at + timedelta(days=14)),
                    "status": offer_status,
                }
            )
            if status == "issued":
                issued_at = decision_at + timedelta(days=rng.randint(1, 5))
                tables["loan_contracts"].append(
                    {
                        "contract_id": next_id(counters, "contract", "LC", 7),
                        "application_id": app_id,
                        "company_id": company.company_id,
                        "amount_rub": approved_amount,
                        "rate_percent": rate,
                        "term_months": term_months,
                        "issued_at": iso_dt(issued_at),
                        "status": "active",
                        "payment_schedule_json": payment_schedule(
                            approved_amount, rate, term_months, issued_at
                        ),
                    }
                )


def document_text(company: Company, document_type: str, application: dict | None = None) -> str:
    header = [
        "СИНТЕТИЧЕСКИЙ ДОКУМЕНТ ДЛЯ ПРОТОТИПА",
        "Не является юридически значимым документом.",
        f"Компания: {company.legal_name}",
        f"ИНН: {company.inn}",
        f"ОГРН: {company.ogrn}",
        f"Адрес: {company.address}",
    ]
    if document_type == "charter":
        body = ["УСТАВ", "Общие положения", "Общество действует на основании настоящего устава."]
    elif document_type == "egrul_extract":
        body = ["ВЫПИСКА ИЗ ЕГРЮЛ", f"Статус: {company.status}", f"ОКВЭД: {company.okved['code']}"]
    elif document_type == "financial_statements":
        body = [
            "БУХГАЛТЕРСКАЯ ОТЧЁТНОСТЬ",
            f"Выручка: {company.annual_revenue_rub} руб.",
            f"Прибыль: {company.net_profit_rub} руб.",
        ]
    elif document_type == "tax_return":
        body = ["НАЛОГОВАЯ ДЕКЛАРАЦИЯ", f"Режим: {company.tax_regime}"]
    elif document_type == "bank_statement":
        body = ["ВЫПИСКА ПО СЧЁТУ", f"Банк: {C.BANKS[0]}", f"Обороты: {company.annual_revenue_rub} руб."]
    elif document_type == "license":
        body = ["ЛИЦЕНЗИЯ", f"Вид деятельности: {company.okved['name']}"]
    elif document_type == "application":
        body = ["ЗАЯВКА НА КРЕДИТ", f"Сумма: {application['requested_amount_rub'] if application else 0} руб."]
    elif document_type == "offer":
        body = ["КРЕДИТНОЕ ПРЕДЛОЖЕНИЕ", f"Сумма: {application['requested_amount_rub'] if application else 0} руб."]
    elif document_type == "loan_contract":
        body = ["КРЕДИТНЫЙ ДОГОВОР", f"Сумма: {application['requested_amount_rub'] if application else 0} руб."]
    else:
        body = ["ДОГОВОР", "Предмет договора: оказание услуг."]
    return "\n".join(header + [""] + body) + "\n"


def make_documents(
    company: Company,
    rng,
    counters: dict[str, int],
    tables: dict,
    document_texts: dict[str, str],
) -> None:
    count = rng.randint(3, 6)
    for document_type in rng.sample(C.DOCUMENT_TYPES[:8], k=min(count, 8)):
        document_id = next_id(counters, "document", "DOC", 7)
        file_name = f"{document_id}_{document_type}.txt"
        file_path = f"documents/{file_name}"
        tables["documents"].append(
            {
                "document_id": document_id,
                "company_id": company.company_id,
                "application_id": None,
                "document_type": document_type,
                "file_name": file_name,
                "file_path": file_path,
                "uploaded_at": iso_dt(C.NOW - timedelta(days=rng.randint(1, 180))),
                "status": weighted_choice(rng, ["verified", "uploaded", "rejected"], [0.75, 0.20, 0.05]),
                "extracted_data_json": {
                    "company_id": company.company_id,
                    "document_type": document_type,
                    "synthetic": True,
                },
            }
        )
        document_texts[file_path] = document_text(company, document_type)

    applications = [row for row in tables["applications"] if row["company_id"] == company.company_id]
    for application in applications:
        if application["status"] not in {"approved", "offer_sent", "offer_accepted", "issued"}:
            continue
        for document_type in ["offer", "loan_contract"] if application["status"] == "issued" else ["offer"]:
            document_id = next_id(counters, "document", "DOC", 7)
            file_name = f"{document_id}_{document_type}.txt"
            file_path = f"documents/{file_name}"
            tables["documents"].append(
                {
                    "document_id": document_id,
                    "company_id": company.company_id,
                    "application_id": application["application_id"],
                    "document_type": document_type,
                    "file_name": file_name,
                    "file_path": file_path,
                    "uploaded_at": application["decision_at"] or application["submitted_at"],
                    "status": "verified",
                    "extracted_data_json": {
                        "application_id": application["application_id"],
                        "document_type": document_type,
                        "synthetic": True,
                    },
                }
            )
            document_texts[file_path] = document_text(company, document_type, application)


def generate_all(seed: int, n_companies: int, months: int = 12) -> tuple[dict[str, list[dict]], dict[str, str]]:
    tables = {table: [] for table in TABLE_ORDER}
    counters: dict[str, int] = {}
    document_texts: dict[str, str] = {}
    used_inn: set[str] = set()
    used_ogrn: set[str] = set()

    for idx in range(1, n_companies + 1):
        rng = make_rng(seed, f"company:{idx}")
        company = make_company(rng, idx, used_inn, used_ogrn)
        tables["companies"].append(company_row(company))

        company.users = make_users(company, rng, counters)
        for user in company.users:
            tables["users"].append(user.__dict__.copy())
        make_founders_and_managers(company, rng, counters, tables)
        make_consents(company, rng, counters, tables)
        make_egrul(company, rng, counters, tables)
        make_sme_and_financials(company, rng, counters, tables)
        make_bank(company, rng, counters, tables, months)
        make_currency_operations(company, rng, counters, tables)
        make_bki(company, rng, counters, tables)
        make_legal_events(company, rng, counters, tables)
        make_assets(company, rng, counters, tables)
        make_state_extras(company, rng, counters, tables)
        make_digital_extras(company, rng, counters, tables, months)
        make_alternative_data(company, rng, counters, tables, months)
        make_accounting(company, rng, counters, tables, months)
        make_market_data(company, rng, counters, tables, months)
        make_applications(company, rng, counters, tables, months)
        make_documents(company, rng, counters, tables, document_texts)

    return tables, document_texts


def validate(tables: dict[str, list[dict]]) -> list[str]:
    errors = []
    company_ids = {row["company_id"] for row in tables["companies"]}
    user_ids = {row["user_id"] for row in tables["users"]}
    account_ids = {row["account_id"] for row in tables["bank_accounts"]}
    report_ids = {row["report_id"] for row in tables["credit_bureau_reports"]}
    application_ids = {row["application_id"] for row in tables["applications"]}

    company_tables = [
        "users",
        "founders",
        "managers",
        "consents",
        "egrul_records",
        "sme_registry",
        "financial_statements",
        "tax_reports",
        "sfr_reports",
        "fns_status",
        "rosstat_indicators",
        "intellectual_property",
        "customs_declarations",
        "gosuslugi_events",
        "rating_agency_ratings",
        "counterparty_checks",
        "business_history",
        "domain_whois",
        "geo_metrics",
        "bank_accounts",
        "currency_operations",
        "bank_products",
        "bank_internal_history",
        "credit_bureau_reports",
        "credit_inquiries",
        "court_cases",
        "enforcement_proceedings",
        "bankruptcy_events",
        "real_estate",
        "vehicles",
        "licenses",
        "tenders",
        "insurance_policies",
        "fuel_cards",
        "telematics",
        "iot_sensors",
        "accounting_entries",
        "management_reports",
        "accounting_systems",
        "marketplace_sales",
        "payment_services",
        "ofd_receipts",
        "warehouse_stock",
        "website_metrics",
        "reputation",
        "hr_metrics",
        "logistics",
        "utilities",
        "mobile_operator",
        "social_media",
        "news_mentions",
        "franchise_contracts",
        "grants_subsidies",
        "certifications",
        "industry_memberships",
        "trade_networks",
        "biometric_checks",
        "self_assessments",
        "collateral_offers",
        "applications",
        "loan_default_events",
        "documents",
        "audit_log",
    ]
    for table in company_tables:
        for row in tables[table]:
            if row.get("company_id") and row["company_id"] not in company_ids:
                errors.append(f"{table}: unknown company_id {row['company_id']}")
                break
    for row in tables["bank_transactions"]:
        if row["account_id"] not in account_ids:
            errors.append(f"bank_transactions: unknown account_id {row['account_id']}")
            break
    for row in tables["currency_operations"]:
        if row["account_id"] not in account_ids:
            errors.append(f"currency_operations: unknown account_id {row['account_id']}")
            break
    for row in tables["credit_bureau_loans"]:
        if row["report_id"] not in report_ids:
            errors.append(f"credit_bureau_loans: unknown report_id {row['report_id']}")
            break
    for row in tables["applications"]:
        if row["user_id"] not in user_ids:
            errors.append(f"applications: unknown user_id {row['user_id']}")
            break
    for row in tables["gosuslugi_events"]:
        if row["user_id"] and row["user_id"] not in user_ids:
            errors.append(f"gosuslugi_events: unknown user_id {row['user_id']}")
            break
    for row in tables["biometric_checks"]:
        if row["user_id"] not in user_ids:
            errors.append(f"biometric_checks: unknown user_id {row['user_id']}")
            break
    vehicle_ids = {row["vehicle_id"] for row in tables["vehicles"]}
    for row in tables["telematics"]:
        if row["vehicle_id"] not in vehicle_ids:
            errors.append(f"telematics: unknown vehicle_id {row['vehicle_id']}")
            break
    for table in [
        "application_events",
        "scoring_results",
        "policy_decisions",
        "offers",
        "self_assessments",
        "collateral_offers",
        "loan_default_events",
    ]:
        for row in tables[table]:
            if row["application_id"] not in application_ids:
                errors.append(f"{table}: unknown application_id {row['application_id']}")
                break
    for table in [
        "companies",
        "users",
        "bank_accounts",
        "bank_transactions",
        "fns_status",
        "rosstat_indicators",
        "counterparty_checks",
        "business_history",
        "management_reports",
        "self_assessments",
        "applications",
    ]:
        if not tables[table]:
            errors.append(f"{table}: empty table")
    return errors
