"""Проверка скоринга на реалистичных профилях МСБ через POST /scoring/batch (без сохранения заявок).

Запуск (бэкенд и ML должны работать):
    cd backend && uv run python ../frontend/scripts/model-check.py
Переменные: API (по умолчанию http://localhost:3001), ADMIN_EMAIL, ADMIN_PASSWORD.
"""
import copy, glob, json, os
import httpx

def P(name, expect, why, *, form='llc', okved='62.01', region='Москва', reg='2016-05-10', emp=30,
      rev, profit, ebitda, debt, exp_m, ar, cash,
      act=1, outst=2_000_000, pay_m=150_000, dpd=0, past_due=False, util=0.2, closed=5, apps=0,
      product='term_loan', amount=3_000_000, term=24, purpose='working_capital', segment='small'):
    inn = '771234567890' if form == 'individual_entrepreneur' else '7712345678'
    ogrn = '318774600123456' if form == 'individual_entrepreneur' else '1157746123456'
    return dict(name=name, expect=expect, why=why, request=dict(
        application=dict(product_type=product, requested_amount_rub=amount, term_months=term, purpose=purpose, segment=segment, submitted_at='2026-10-25T10:00:00Z'),
        company=dict(inn=inn, ogrn=ogrn, legal_name=name, legal_form=form, okved=okved, region=region, registration_date=f'{reg}T00:00:00Z', employee_count=emp),
        financials=dict(annual_revenue_rub=rev, annual_net_profit_rub=profit, ebitda_rub=ebitda, total_debt_rub=debt, monthly_revenue_rub=rev // 12,
                        monthly_expenses_rub=exp_m, accounts_receivable_rub=ar, cash_balance_rub=cash, period_end='2026-09-30T00:00:00Z'),
        credit_history=dict(active_obligations_count=act, total_outstanding_rub=outst, monthly_debt_payments_rub=pay_m, max_days_past_due_12m=dpd,
                            has_current_past_due=past_due, credit_utilization=util, closed_obligations_count=closed, applications_last_6m=apps)))

PROFILES = [
    # ── Хорошие: ожидаем одобрение
    P('IT-интегратор, 10 лет', 'одобрение', 'большая стабильная выручка, маленький долг, без просрочек',
      okved='62.01', reg='2016-03-01', emp=45, rev=120_000_000, profit=18_000_000, ebitda=24_000_000, debt=6_000_000, exp_m=8_200_000, ar=6_000_000, cash=9_000_000,
      act=1, outst=3_000_000, pay_m=180_000, util=0.25, closed=6, amount=5_000_000, term=24, purpose='equipment'),
    P('Сеть пекарен (ИП), 9 лет', 'одобрение', 'прибыльный ритейл, кредит меньше 10% выручки',
      form='individual_entrepreneur', okved='10.71', region='Казань', reg='2017-06-15', emp=38, rev=60_000_000, profit=7_200_000, ebitda=10_000_000, debt=3_000_000, exp_m=4_300_000, ar=500_000, cash=3_500_000,
      act=1, outst=1_500_000, pay_m=90_000, util=0.3, closed=4, amount=4_000_000, term=18),
    P('Завод металлоконструкций, 15 лет', 'одобрение', 'крупный, умеренная нагрузка, лизинг станков',
      okved='25.11', region='Екатеринбург', reg='2011-02-01', emp=120, rev=300_000_000, profit=24_000_000, ebitda=42_000_000, debt=60_000_000, exp_m=22_500_000, ar=30_000_000, cash=15_000_000,
      act=3, outst=45_000_000, pay_m=2_200_000, util=0.45, closed=12, apps=1, product='leasing', amount=20_000_000, term=48, purpose='equipment'),
    P('Кофейня (ИП), 6 лет', 'одобрение', 'небольшой, но прибыльный, просит овердрафт 1 млн',
      form='individual_entrepreneur', okved='56.10', region='Санкт-Петербург', reg='2020-04-01', emp=9, rev=18_000_000, profit=2_400_000, ebitda=3_000_000, debt=500_000, exp_m=1_250_000, ar=0, cash=1_200_000,
      act=1, outst=400_000, pay_m=35_000, util=0.15, closed=3, product='overdraft', amount=1_000_000, term=12, segment='micro'),
    # ── Средние: скорее одобрение, возможно с условиями
    P('Грузоперевозки, 7 лет', 'одобрение или проверка', 'заметный долг, была короткая просрочка',
      okved='49.41', region='Новосибирск', reg='2019-01-20', emp=40, rev=40_000_000, profit=2_000_000, ebitda=5_000_000, debt=15_000_000, exp_m=3_100_000, ar=4_000_000, cash=1_000_000,
      act=3, outst=12_000_000, pay_m=900_000, dpd=10, util=0.6, closed=4, apps=2, amount=5_000_000, term=24),
    P('Стройподрядчик, 5 лет', 'проверка', 'рентабельность 2%, лимиты загружены на 60%, много заявок',
      okved='41.20', region='Краснодар', reg='2021-03-01', emp=60, rev=80_000_000, profit=1_600_000, ebitda=4_000_000, debt=25_000_000, exp_m=6_400_000, ar=15_000_000, cash=1_500_000,
      act=4, outst=20_000_000, pay_m=1_500_000, dpd=15, util=0.6, closed=3, apps=4, amount=10_000_000, term=24),
    P('Молодая IT-студия, 1,5 года', 'проверка', 'бизнесу мало лет, просит 40% годовой выручки',
      okved='62.01', reg='2025-04-01', emp=8, rev=12_000_000, profit=1_500_000, ebitda=2_000_000, debt=0, exp_m=850_000, ar=1_500_000, cash=800_000,
      act=0, outst=0, pay_m=0, util=0.0, closed=0, apps=1, amount=5_000_000, term=24, segment='micro'),
    P('Продавец на маркетплейсах, 3 года', 'одобрение или проверка', 'большая дебиторка, мало денег на счетах',
      form='individual_entrepreneur', okved='47.91', reg='2023-05-01', emp=6, rev=25_000_000, profit=1_800_000, ebitda=2_500_000, debt=2_000_000, exp_m=1_900_000, ar=6_000_000, cash=300_000,
      act=2, outst=1_800_000, pay_m=160_000, util=0.5, closed=2, apps=2, product='microloan', amount=2_000_000, term=12, segment='micro'),
    # ── Пограничные: ожидаем другие условия
    P('Оптовик, просит 70% выручки', 'одобрение с условием (меньше сумма)', 'сумма > 60% годовой выручки и > 3 млн',
      okved='46.69', region='Ростов-на-Дону', reg='2014-09-01', emp=35, rev=30_000_000, profit=3_000_000, ebitda=4_500_000, debt=2_000_000, exp_m=2_200_000, ar=3_000_000, cash=2_000_000,
      act=1, outst=1_500_000, pay_m=100_000, util=0.3, closed=6, product='credit_line', amount=21_000_000, term=24, purpose='expansion'),
    P('Ресторан, долги съедают выручку', 'ручная проверка', 'платежи по кредитам ≈ 60% месячной выручки',
      okved='56.10', region='Сочи', reg='2018-05-01', emp=30, rev=36_000_000, profit=900_000, ebitda=3_000_000, debt=14_000_000, exp_m=2_700_000, ar=200_000, cash=500_000,
      act=4, outst=13_000_000, pay_m=1_800_000, dpd=5, util=0.7, closed=3, apps=2, product='overdraft', amount=2_000_000, term=12),
    # ── Плохие: ожидаем отказ
    P('Сейчас в просрочке', 'отказ', 'текущая просрочка по кредиту',
      okved='41.20', region='Новосибирск', reg='2020-02-20', emp=18, rev=18_000_000, profit=-600_000, ebitda=400_000, debt=7_500_000, exp_m=1_560_000, ar=2_600_000, cash=150_000,
      act=3, outst=6_900_000, pay_m=420_000, dpd=96, past_due=True, util=0.91, closed=2, apps=5, amount=4_000_000, term=24, purpose='refinancing'),
    P('Была просрочка 75 дней', 'отказ', 'просрочка 60+ дней за последний год',
      okved='45.20', region='Самара', reg='2017-01-01', emp=20, rev=35_000_000, profit=2_000_000, ebitda=3_500_000, debt=6_000_000, exp_m=2_700_000, ar=2_000_000, cash=800_000,
      act=2, outst=5_000_000, pay_m=350_000, dpd=75, util=0.5, closed=4, apps=2, amount=3_000_000, term=24),
    P('Убыточная, долг больше выручки', 'отказ', 'убыток, долг 120% выручки, лимиты выбраны',
      okved='68.20', region='Москва', reg='2019-07-01', emp=12, rev=20_000_000, profit=-4_000_000, ebitda=-1_500_000, debt=24_000_000, exp_m=2_000_000, ar=1_000_000, cash=100_000,
      act=6, outst=22_000_000, pay_m=1_300_000, dpd=30, util=0.95, closed=1, apps=6, amount=5_000_000, term=36, purpose='refinancing'),
    P('Просит втрое больше выручки', 'отказ или меньшая сумма', 'кредит 300% годовой выручки',
      form='individual_entrepreneur', okved='47.11', region='Тверь', reg='2022-03-01', emp=4, rev=5_000_000, profit=400_000, ebitda=600_000, debt=500_000, exp_m=380_000, ar=100_000, cash=200_000,
      act=1, outst=400_000, pay_m=40_000, util=0.4, closed=1, apps=3, amount=15_000_000, term=36, segment='micro', purpose='expansion'),
]

# Примеры из репозитория (examples/*.json) — в формате proto-энумов, переводим в API
ENUM = {'PRODUCT_TYPE_TERM_LOAN': 'term_loan', 'PRODUCT_TYPE_MICROLOAN': 'microloan', 'PRODUCT_TYPE_OVERDRAFT': 'overdraft', 'PRODUCT_TYPE_CREDIT_LINE': 'credit_line', 'PRODUCT_TYPE_LEASING': 'leasing',
        'FINANCING_PURPOSE_EQUIPMENT': 'equipment', 'FINANCING_PURPOSE_WORKING_CAPITAL': 'working_capital', 'FINANCING_PURPOSE_EXPANSION': 'expansion', 'FINANCING_PURPOSE_REFINANCING': 'refinancing', 'FINANCING_PURPOSE_OTHER': 'other',
        'BUSINESS_SEGMENT_SMALL': 'small', 'BUSINESS_SEGMENT_MICRO': 'micro', 'LEGAL_FORM_LLC': 'llc', 'LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR': 'individual_entrepreneur', 'LEGAL_FORM_JOINT_STOCK_COMPANY': 'joint_stock_company'}

def from_example(path):
    d = json.load(open(path))
    d.pop('application_id', None)
    def conv(o):
        if isinstance(o, dict): return {k: conv(v) for k, v in o.items()}
        if isinstance(o, str) and o in ENUM: return ENUM[o]
        return o
    d = conv(d)
    d['application'].setdefault('submitted_at', '2026-10-25T10:00:00Z')
    return d


B = os.environ.get('API', 'http://localhost:3001')
ADMIN = (os.environ.get('ADMIN_EMAIL', 'admin@admin.com'), os.environ.get('ADMIN_PASSWORD', 'admin'))
c = httpx.Client(base_url=B, timeout=60)
tok = c.post('/auth/login', json={'email': ADMIN[0], 'password': ADMIN[1]}).json()['access_token']
H = {'Authorization': f'Bearer {tok}'}

def score(reqs):
    r = c.post('/scoring/batch', headers=H, json={'applications': reqs})
    r.raise_for_status()
    return r.json()['results']

out = {'profiles': [], 'examples': [], 'sweeps': {}}

res = score([p['request'] for p in PROFILES])
for p, s in zip(PROFILES, res):
    d = s['decision']
    out['profiles'].append(dict(name=p['name'], expect=p['expect'], why=p['why'], score=s['score'], pd=round(s['pd'], 4), grade=s['risk_grade'],
                                decision=d['decision'], reasons=d['reason_codes'], conditions=d['conditions'],
                                top=[(r['feature'], r['impact'], round(r['contribution'], 3)) for r in s['reason_codes']]))

ex_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'examples')
ex = sorted(glob.glob(f'{ex_root}/*.json'))
for path, s in zip(ex, score([from_example(x) for x in ex])):
    out['examples'].append(dict(file=os.path.basename(path), score=s['score'], pd=round(s['pd'], 4), grade=s['risk_grade'], decision=s['decision']['decision'], reasons=s['decision']['reason_codes']))

# Чувствительность: меняем один фактор у хорошей базовой компании
base = PROFILES[0]['request']
def sweep(name, setter, values):
    reqs = []
    for v in values:
        r = copy.deepcopy(base); setter(r, v); reqs.append(r)
    out['sweeps'][name] = [(v, s['score'], round(s['pd'], 4), s['risk_grade'], s['decision']['decision']) for v, s in zip(values, score(reqs))]

ch = lambda k: (lambda r, v: r['credit_history'].__setitem__(k, v))
fi = lambda k: (lambda r, v: r['financials'].__setitem__(k, v))
sweep('Просрочка за год, дней', ch('max_days_past_due_12m'), [0, 15, 30, 59, 60, 90])
sweep('Загрузка лимитов', ch('credit_utilization'), [0.0, 0.25, 0.5, 0.75, 0.95])
sweep('Платежи по долгам в месяц, ₽', ch('monthly_debt_payments_rub'), [0, 180_000, 1_000_000, 3_000_000, 6_000_000])
sweep('Заявок за 6 мес', ch('applications_last_6m'), [0, 2, 5, 10])
sweep('Запрошенная сумма, ₽', lambda r, v: r['application'].__setitem__('requested_amount_rub', v), [1_000_000, 5_000_000, 30_000_000, 75_000_000, 150_000_000])
sweep('Чистая прибыль за год, ₽', fi('annual_net_profit_rub'), [18_000_000, 6_000_000, 0, -6_000_000, -20_000_000])
sweep('Общий долг, ₽', fi('total_debt_rub'), [0, 6_000_000, 30_000_000, 90_000_000, 150_000_000])
sweep('Деньги на счетах, ₽', fi('cash_balance_rub'), [0, 1_000_000, 9_000_000, 30_000_000])
sweep('Дата регистрации', lambda r, v: r['company'].__setitem__('registration_date', v), ['2026-06-01T00:00:00Z', '2025-06-01T00:00:00Z', '2023-01-01T00:00:00Z', '2016-03-01T00:00:00Z', '2006-01-01T00:00:00Z'])
sweep('Сотрудников', lambda r, v: r['company'].__setitem__('employee_count', v), [1, 5, 45, 200, 1000])
sweep('Текущая просрочка', ch('has_current_past_due'), [False, True])


print('== Профили')
for p in out['profiles']:
    print(f"{p['name'][:34]:34} | ждём: {p['expect'][:26]:26} | {p['decision']:24} | {p['score']:4} | PD {p['pd']*100:5.1f}% | {p['grade']} | {','.join(p['reasons'])}")
print('== Примеры из examples/')
for e in out['examples']:
    print(f"{e['file']:28} | {e['decision']:24} | {e['score']:4} | PD {e['pd']*100:5.1f}% | {e['grade']} | {','.join(e['reasons'])}")
print('== Чувствительность (база: IT-интегратор)')
for k, rows in out['sweeps'].items():
    print(k); [print('   ', r) for r in rows]
print('== Топ-факторы у первых трёх профилей')
for p in out['profiles'][:3]:
    print(p['name'], p['top'])
