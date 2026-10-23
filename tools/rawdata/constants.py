from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "raw"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
SCHEMA_VERSION = "1.1"
MODEL_VERSION = "scorecard-linear-v1"

TABLE_ORDER = [
    "companies",
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
    "bank_transactions",
    "currency_operations",
    "bank_products",
    "bank_internal_history",
    "credit_bureau_reports",
    "credit_bureau_loans",
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
    "applications",
    "self_assessments",
    "collateral_offers",
    "application_events",
    "scoring_results",
    "policy_decisions",
    "offers",
    "loan_contracts",
    "loan_default_events",
    "documents",
    "audit_log",
]

JSON_FIELDS = {
    "egrul_records": ["okved_additional", "founders_json", "managers_json", "changes_json"],
    "sme_registry": ["benefits_json"],
    "sfr_reports": ["benefits_json"],
    "fns_status": ["risk_flags_json"],
    "customs_declarations": ["goods_json"],
    "gosuslugi_events": ["payload_json"],
    "counterparty_checks": ["risk_flags_json"],
    "business_history": ["payload_json"],
    "bank_internal_history": ["aml_flags_json", "risk_flags_json"],
    "real_estate": ["encumbrances_json"],
    "vehicles": ["restrictions_json"],
    "insurance_policies": ["coverage_json"],
    "website_metrics": ["traffic_sources_json"],
    "logistics": ["regions_json"],
    "franchise_contracts": ["terms_json"],
    "self_assessments": ["obligations_json"],
    "scoring_results": ["reason_codes_json"],
    "policy_decisions": ["reason_codes_json", "conditions_json"],
    "offers": ["conditions_json"],
    "loan_contracts": ["payment_schedule_json"],
    "documents": ["extracted_data_json"],
    "audit_log": ["payload_json"],
}

LEGAL_FORMS = ["llc", "ip", "jsc"]
LEGAL_FORM_LABELS = {"llc": "ООО", "ip": "ИП", "jsc": "АО"}
SEGMENTS = ["micro", "small"]
PRODUCTS = ["microloan", "term_loan", "overdraft", "credit_line", "leasing"]
PURPOSES = ["working_capital", "equipment", "expansion", "refinancing", "other"]
APPLICATION_STATUSES = [
    "draft",
    "submitted",
    "data_check",
    "scoring",
    "manual_review",
    "approved",
    "offer_sent",
    "offer_accepted",
    "issued",
    "rejected",
    "withdrawn",
]

BANKS = [
    "АО «Альфа-Банк»",
    "ПАО «Сбербанк»",
    "ПАО «ВТБ»",
    "АО «Тинькофф Банк»",
    "ПАО «Промсвязьбанк»",
    "АО «Райффайзенбанк»",
    "ПАО «Банк «Санкт-Петербург»",
    "АО «Россельхозбанк»",
]

BKI_NAMES = ["НБКИ", "ОКБ", "Скоринг Бюро"]

REGIONS = [
    {"name": "Москва", "city": "Москва", "code": "77", "risk": 0.10},
    {"name": "Санкт-Петербург", "city": "Санкт-Петербург", "code": "78", "risk": 0.15},
    {"name": "Московская область", "city": "Химки", "code": "50", "risk": 0.20},
    {"name": "Республика Татарстан", "city": "Казань", "code": "16", "risk": 0.25},
    {"name": "Свердловская область", "city": "Екатеринбург", "code": "66", "risk": 0.30},
    {"name": "Новосибирская область", "city": "Новосибирск", "code": "54", "risk": 0.30},
    {"name": "Краснодарский край", "city": "Краснодар", "code": "23", "risk": 0.32},
    {"name": "Ростовская область", "city": "Ростов-на-Дону", "code": "61", "risk": 0.35},
    {"name": "Республика Башкортостан", "city": "Уфа", "code": "02", "risk": 0.32},
    {"name": "Приморский край", "city": "Владивосток", "code": "25", "risk": 0.38},
    {"name": "Самарская область", "city": "Самара", "code": "63", "risk": 0.30},
    {"name": "Челябинская область", "city": "Челябинск", "code": "74", "risk": 0.33},
]

OKVED_PROFILES = [
    {"code": "62.01", "name": "Разработка компьютерного ПО", "industry": "IT", "risk": 0.20},
    {"code": "47.11", "name": "Розничная торговля", "industry": "Ритейл", "risk": 0.50},
    {"code": "46.90", "name": "Оптовая торговля", "industry": "Опт", "risk": 0.40},
    {"code": "56.10", "name": "Рестораны и кафе", "industry": "HoReCa", "risk": 0.60},
    {"code": "43.21", "name": "Электромонтажные работы", "industry": "Строительство", "risk": 0.55},
    {"code": "41.20", "name": "Строительство зданий", "industry": "Строительство", "risk": 0.60},
    {"code": "49.41", "name": "Грузоперевозки", "industry": "Логистика", "risk": 0.50},
    {"code": "10.71", "name": "Производство хлеба", "industry": "Производство", "risk": 0.45},
    {"code": "25.62", "name": "Металлообработка", "industry": "Производство", "risk": 0.45},
    {"code": "68.20", "name": "Аренда недвижимости", "industry": "Недвижимость", "risk": 0.45},
    {"code": "69.10", "name": "Юридические услуги", "industry": "Услуги", "risk": 0.30},
    {"code": "71.12", "name": "Инженерные изыскания", "industry": "Услуги", "risk": 0.35},
    {"code": "73.11", "name": "Рекламные агентства", "industry": "Маркетинг", "risk": 0.40},
    {"code": "74.20", "name": "Дизайн и фотография", "industry": "Услуги", "risk": 0.35},
    {"code": "86.21", "name": "Медицинская практика", "industry": "Медицина", "risk": 0.30},
    {"code": "96.02", "name": "Парикмахерские и салоны", "industry": "Бытовые услуги", "risk": 0.50},
    {"code": "55.10", "name": "Гостиницы", "industry": "Туризм", "risk": 0.55},
    {"code": "01.11", "name": "Растениеводство", "industry": "Сельское хозяйство", "risk": 0.60},
    {"code": "02.10", "name": "Лесозаготовка", "industry": "Сельское хозяйство", "risk": 0.60},
    {"code": "28.99", "name": "Производство оборудования", "industry": "Производство", "risk": 0.45},
    {"code": "33.12", "name": "Ремонт машин", "industry": "Услуги", "risk": 0.45},
    {"code": "45.20", "name": "Автосервис", "industry": "Авто", "risk": 0.50},
    {"code": "52.29", "name": "Транспортная обработка", "industry": "Логистика", "risk": 0.45},
    {"code": "63.11", "name": "Обработка данных", "industry": "IT", "risk": 0.25},
    {"code": "70.22", "name": "Бизнес-консультирование", "industry": "Услуги", "risk": 0.30},
]

COMPANY_STEMS = [
    "Вектор", "Ромашка", "Прогресс", "Альянс", "Горизонт", "Мастер", "Сибирь",
    "Урал", "Сфера", "Кварц", "Меркурий", "Орион", "Прайм", "Ресурс", "Стандарт",
    "Технологии", "Торг", "Сервис", "Групп", "Логистик", "Строй", "Агро", "Медиа",
    "Капитал", "Инвест", "Партнёр", "Лидер", "Оптима", "Нова", "Бизнес",
]
COMPANY_SUFFIXES = [
    "Групп", "Трейд", "Сервис", "Логистик", "Строй", "Агро", "Медиа", "Капитал",
    "Плюс", "Про", "Технологии", "Ресурс", "Опт", "Ритейл", "Индустрия",
]

LAST_NAMES_M = [
    "Смирнов", "Иванов", "Кузнецов", "Соколов", "Попов", "Лебедев", "Козлов",
    "Новиков", "Морозов", "Петров", "Волков", "Соловьёв", "Васильев", "Зайцев",
    "Павлов", "Семёнов", "Голубев", "Виноградов", "Богданов", "Воробьёв",
    "Фёдоров", "Михайлов", "Беляев", "Тарасов", "Белов", "Комаров", "Орлов",
    "Киселёв", "Макаров", "Андреев",
]
FIRST_NAMES_M = [
    "Александр", "Алексей", "Андрей", "Антон", "Артём", "Борис", "Вадим",
    "Василий", "Виктор", "Владимир", "Геннадий", "Георгий", "Денис", "Дмитрий",
    "Евгений", "Иван", "Игорь", "Илья", "Кирилл", "Константин", "Максим",
    "Михаил", "Никита", "Николай", "Олег", "Павел", "Пётр", "Роман", "Сергей",
    "Станислав", "Степан", "Тимур", "Фёдор", "Юрий", "Ярослав",
]
PATRONYMICS_M = [
    "Александрович", "Алексеевич", "Андреевич", "Антонович", "Артёмович",
    "Борисович", "Вадимович", "Васильевич", "Викторович", "Владимирович",
    "Геннадьевич", "Георгиевич", "Денисович", "Дмитриевич", "Евгеньевич",
    "Иванович", "Игоревич", "Ильич", "Кириллович", "Константинович",
    "Максимович", "Михайлович", "Никитич", "Николаевич", "Олегович",
    "Павлович", "Петрович", "Романович", "Сергеевич", "Станиславович",
    "Степанович", "Тимурович", "Фёдорович", "Юрьевич", "Ярославович",
]
LAST_NAMES_F = [
    "Смирнова", "Иванова", "Кузнецова", "Соколова", "Попова", "Лебедева",
    "Козлова", "Новикова", "Морозова", "Петрова", "Волкова", "Соловьёва",
    "Васильева", "Зайцева", "Павлова", "Семёнова", "Голубева", "Виноградова",
    "Богданова", "Воробьёва", "Фёдорова", "Михайлова", "Беляева", "Тарасова",
    "Белова", "Комарова", "Орлова", "Киселёва", "Макарова", "Андреева",
]
FIRST_NAMES_F = [
    "Александра", "Алина", "Анастасия", "Анна", "Валентина", "Валерия",
    "Вера", "Виктория", "Галина", "Дарья", "Евгения", "Екатерина", "Елена",
    "Елизавета", "Жанна", "Зоя", "Инна", "Ирина", "Ксения", "Лариса",
    "Людмила", "Маргарита", "Марина", "Мария", "Надежда", "Наталья",
    "Оксана", "Ольга", "Полина", "Светлана", "София", "Татьяна", "Ульяна",
    "Юлия", "Яна",
]
PATRONYMICS_F = [
    "Александровна", "Алексеевна", "Андреевна", "Антоновна", "Артёмовна",
    "Борисовна", "Вадимовна", "Васильевна", "Викторовна", "Владимировна",
    "Геннадьевна", "Георгиевна", "Денисовна", "Дмитриевна", "Евгеньевна",
    "Ивановна", "Игоревна", "Ильинична", "Кирилловна", "Константиновна",
    "Максимовна", "Михайловна", "Никитична", "Николаевна", "Олеговна",
    "Павловна", "Петровна", "Романовна", "Сергеевна", "Станиславовна",
    "Степановна", "Тимуровна", "Фёдоровна", "Юрьевна", "Ярославовна",
]

STREETS = [
    "Ленина", "Пушкина", "Гагарина", "Мира", "Советская", "Центральная",
    "Молодёжная", "Школьная", "Садовая", "Лесная", "Набережная", "Заводская",
    "Промышленная", "Торговая", "Строителей", "Космонавтов", "Победы",
    "Кирова", "Московская", "Новая", "Октябрьская", "Первомайская",
]

COUNTERPARTY_STEMS = [
    "Снабжение", "Логистика", "ОптТорг", "СтройМатериалы", "Продукт", "Техника",
    "Упаковка", "Мебель", "Электрика", "Инструмент", "АгроТрейд", "Металл",
    "Химия", "Транспорт", "Сервис", "Партнёр", "Ритейл", "Комплект", "Ресурс",
]
COUNTERPARTY_CUSTOMERS = [
    "ООО «Клиент-1»", "ООО «Клиент-2»", "ООО «Розница»", "ООО «Сеть»",
    "ИП Орлов", "ИП Соколова", "ООО «Покупатель»", "ООО «Маркет»",
    "ООО «Торговый дом»", "АО «Корпорация»",
]

SUPPLIER_NAMES = [
    "ООО «Снабжение+»", "ООО «ОптТорг»", "ООО «СтройМатериалы»",
    "ООО «Продукт»", "ООО «Техника»", "ООО «Упаковка»", "ООО «Электрика»",
    "ООО «Инструмент»", "ООО «АгроТрейд»", "ООО «Металл»", "ООО «Химия»",
    "ООО «Комплект»", "ООО «Ресурс»",
]

BANK_COUNTERPARTIES = [
    "УФК по г. Москве",
    "ИФНС России № 1",
    "ИФНС России № 2",
    "ГУ МВД России",
    "Арендодатель",
    "Энергосбыт",
    "Водоканал",
    "Теплосеть",
    "Оператор связи",
]

TAX_TYPES = {
    "osn": ["НДС", "Налог на прибыль", "НДФЛ", "Страховые взносы"],
    "usn": ["УСН", "НДФЛ", "Страховые взносы"],
    "patent": ["Патент", "НДФЛ", "Страховые взносы"],
    "eshn": ["ЕСХН", "НДФЛ", "Страховые взносы"],
}

COURT_CATEGORIES = [
    "Взыскание задолженности",
    "Спор по договору поставки",
    "Спор по договору подряда",
    "Налоговый спор",
    "Трудовой спор",
    "Административное дело",
    "Корпоративный спор",
    "Банкротство",
]

COURT_OUTCOMES = ["Удовлетворено", "Отказано", "Частично удовлетворено", "Мировое соглашение", "На рассмотрении"]

ENFORCEMENT_SUBJECTS = [
    "Взыскание задолженности",
    "Взыскание налогов",
    "Взыскание штрафа",
    "Исполнение судебного акта",
    "Взыскание по договору",
]

PROPERTY_TYPES = ["Офис", "Склад", "Торговое помещение", "Производственное помещение", "Земельный участок"]
OWNERSHIP_TYPES = ["Собственность", "Аренда", "Оперативное управление"]
VEHICLE_BRANDS = ["ГАЗ", "КАМАЗ", "Lada", "Toyota", "Hyundai", "Ford", "MAN", "Scania", "Volvo", "Mercedes-Benz"]
VEHICLE_TYPES = ["Легковой автомобиль", "Грузовой автомобиль", "Спецтехника", "Автобус"]

LICENSE_TYPES = {
    "Медицина": ["Медицинская деятельность"],
    "Сельское хозяйство": ["Производство и оборот этилового спирта", "Ветеринарная деятельность"],
    "Производство": ["Эксплуатация взрывопожароопасных объектов", "Производство лекарственных средств"],
    "Логистика": ["Перевозка пассажиров", "Транспортная деятельность"],
    "HoReCa": ["Розничная продажа алкоголя"],
    "Ритейл": ["Розничная продажа алкоголя"],
    "IT": ["Телекоммуникационные услуги"],
    "Бытовые услуги": ["Бытовые услуги"],
}
LICENSE_REGULATORS = [
    "Росздравнадзор", "Росалкогольрегулирование", "Ространснадзор",
    "Ростехнадзор", "Россельхознадзор", "Роскомнадзор", "МЧС России",
]

MCC_CODES = ["5411", "5812", "5912", "5999", "7011", "7230", "8099", "5399"]
TRAFFIC_SOURCES = ["organic", "direct", "advertising", "social", "marketplace", "referral"]
MARKETPLACES = ["Ozon", "Wildberries", "Яндекс Маркет", "Avito"]
REPUTATION_SOURCES = ["Яндекс Карты", "2ГИС", "Google Maps", "Отзовик"]
NEWS_SOURCES = ["Ведомости", "Коммерсантъ", "РБК", "Отраслевой портал", "Региональные новости"]
SOCIAL_PLATFORMS = ["ВКонтакте", "Telegram", "Одноклассники"]
MOBILE_OPERATORS = ["МТС", "Билайн", "МегаФон", "Т2"]
ACCOUNTING_ACCOUNTS = {
    "51": "Расчётные счета",
    "62": "Расчёты с покупателями",
    "60": "Расчёты с поставщиками",
    "70": "Расчёты с персоналом по оплате труда",
    "68": "Расчёты по налогам и сборам",
    "69": "Расчёты по социальному страхованию",
    "10": "Материалы",
    "41": "Товары",
    "90": "Продажи",
    "91": "Прочие доходы и расходы",
    "99": "Прибыли и убытки",
    "76": "Прочие дебиторы и кредиторы",
}
DOCUMENT_TYPES = [
    "charter",
    "egrul_extract",
    "financial_statements",
    "tax_return",
    "bank_statement",
    "license",
    "contract",
    "application",
    "offer",
    "loan_contract",
]
CONSENT_TYPES = [
    "personal_data",
    "credit_history",
    "bank_secrecy",
    "tax_secrecy",
    "government_services",
    "counterparty_check",
    "electronic_signature",
    "scoring",
]
PURPOSE_LABELS = {
    "working_capital": "Пополнение оборотных средств",
    "equipment": "Приобретение оборудования",
    "expansion": "Расширение бизнеса",
    "refinancing": "Рефинансирование",
    "other": "Иные цели",
}
PRODUCT_LABELS = {
    "microloan": "Микрокредит",
    "term_loan": "Срочный кредит",
    "overdraft": "Овердрафт",
    "credit_line": "Кредитная линия",
    "leasing": "Лизинг",
}

COLLATERAL_TYPES = [
    "Недвижимость",
    "Транспорт",
    "Оборудование",
    "Товары в обороте",
    "Поручительство",
    "Залог прав",
]
COLLATERAL_OWNERSHIP = ["Собственность", "Аренда", "Совместная собственность"]

CHECK_SERVICES = ["Контур.Фокус", "СПАРК", "Casebook", "Rusprofile", "СБИС"]
COUNTERPARTY_RISK_FLAGS = [
    "mass_address",
    "mass_manager",
    "recent_director_change",
    "negative_news",
    "court_cases",
    "tax_debt",
    "related_parties",
    "no_activity",
]

FNS_RISK_FLAGS = [
    "tax_debt",
    "blocked_account",
    "late_tax_payments",
    "cash_intensive",
    "unreliable_record",
    "special_regime",
    "vat_gap",
    "high_risk_okved",
]
ROSSTAT_INDICATORS = [
    {"indicator": "Индекс промышленного производства", "unit": "percent"},
    {"indicator": "Оборот розничной торговли", "unit": "percent"},
    {"indicator": "Средняя заработная плата", "unit": "rub"},
    {"indicator": "Инвестиции в основной капитал", "unit": "percent"},
]
IP_TYPES = ["patent", "trademark", "software"]
IP_STATUSES = ["active", "pending", "expired", "rejected"]
CUSTOMS_COUNTRIES = ["Казахстан", "Беларусь", "Китай", "Турция", "ОАЭ", "Узбекистан", "Армения"]
CUSTOMS_HS_CODES = ["8471", "8708", "7214", "9403", "2202", "6204", "8517", "3926"]
CUSTOMS_GOODS = [
    "Комплектующие для оборудования",
    "Транспортные средства",
    "Металлопрокат",
    "Мебель",
    "Напитки",
    "Одежда",
    "Электроника",
    "Полимерные изделия",
]
GOSUSLUGI_SERVICES = [
    "Регистрация юридического лица",
    "Изменение сведений ЕГРЮЛ",
    "Получение лицензии",
    "Налоговая декларация",
    "Заявка на субсидию",
    "Выписка из ЕГРН",
    "Регистрация транспортного средства",
]
RATING_AGENCIES = ["Эксперт РА", "АКРА", "НКР", "НИК"]
RATING_VALUES = ["BB-", "BB", "BB+", "BBB-", "BBB", "BBB+", "A-"]
RATING_OUTLOOKS = ["стабильный", "позитивный", "негативный", "развивающийся"]
ACCOUNTING_SYSTEMS = [
    "1С:Бухгалтерия",
    "Контур.Эльба",
    "СБИС",
    "Моё дело",
    "Точка Бухгалтерия",
    "Битрикс24",
]
PAYMENT_PROVIDERS = [
    "ЮKassa",
    "Тинькофф Касса",
    "Сбербанк Эквайринг",
    "Альфа-Касса",
    "Robokassa",
    "CloudPayments",
]
INSURANCE_TYPES = ["КАСКО", "ОСАГО", "Имущество", "Ответственность", "Жизнь и здоровье", "Грузоперевозки"]
INSURERS = ["АльфаСтрахование", "Ингосстрах", "Согаз", "РЕСО-Гарантия", "ВСК", "Росгосстрах"]
FUEL_PROVIDERS = ["Лукойл", "Газпромнефть", "Роснефть", "Татнефть", "Shell"]
TELEMATICS_PROVIDERS = ["АвтоГРАФ", "Wialon", "ГЛОНАСС-М", "Omnicomm"]
IOT_SENSORS = [
    {"sensor_type": "Электросчётчик", "metric_name": "Потребление электроэнергии", "unit": "kWh"},
    {"sensor_type": "Датчик температуры", "metric_name": "Температура склада", "unit": "C"},
    {"sensor_type": "Датчик вибрации", "metric_name": "Вибрация оборудования", "unit": "mm/s"},
    {"sensor_type": "Счётчик воды", "metric_name": "Потребление воды", "unit": "m3"},
    {"sensor_type": "GPS-трекер", "metric_name": "Пробег", "unit": "km"},
]
FRANCHISORS = ["Газель.Бизнес", "Fix Price", "220 Вольт", "Инвитро", "Шоколадница", "Додо Пицца"]
GRANT_PROGRAMS = [
    "Фонд содействия инновациям",
    "Мой бизнес",
    "Центр занятости",
    "Российский экспортный центр",
    "Корпорация МСП",
]
CERTIFICATION_STANDARDS = ["ISO 9001", "ISO 14001", "ISO 22000", "ГОСТ Р", "ХАССП", "ISO 45001"]
CERTIFICATION_BODIES = ["Ростест", "TÜV", "SGS", "Бюро Веритас", "Российский Регистр"]
ASSOCIATIONS = ["ОПОРА РОССИИ", "Деловая Россия", "ТПП РФ", "АКОРТ", "РСПП"]
TRADE_NETWORKS = ["X5 Group", "Магнит", "Лента", "Ашан", "Метро", "ВкусВилл"]
BIOMETRIC_TYPES = ["face_match", "liveness", "document_check", "voice_match"]
BIOMETRIC_PROVIDERS = ["VisionLabs", "СберБиометрия", "ID R&D", "Speech Technology Center"]
CREDIT_INQUIRY_PURPOSES = ["Новая заявка", "Пересмотр лимита", "Мониторинг", "Рефинансирование"]
CURRENCY_RATES = {"USD": 92.5, "EUR": 100.2, "CNY": 12.8, "KZT": 0.19, "BYN": 28.4, "TRY": 2.7, "AED": 25.2}
