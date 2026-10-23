// Каталог продуктов и целей — общий контракт фронтенда и бэкенда
import type { BusinessGoal, Product, ProductCode, Reason } from './types';

export const PRODUCTS: Product[] = [
  {
    code: 'working_capital',
    name: 'Оборотный кредит',
    kind: 'loan',
    suits: 'Закупка товара и сырья, исполнение контракта, запасы к сезону',
    amountMin: 500_000,
    amountMax: 5_000_000,
    termMin: 6,
    termMax: 18,
    ratePct: 24,
    fees: [{ name: 'Комиссия за выдачу', pct: 1 }],
    collateral: 'Без залога. Поручительство владельца — по решению банка',
  },
  {
    code: 'overdraft',
    name: 'Овердрафт',
    kind: 'limit',
    suits: 'Кассовые разрывы: клиент заплатит позже, а платить нужно сейчас',
    amountMin: 300_000,
    amountMax: 3_000_000,
    termMin: 3,
    termMax: 12,
    ratePct: 27,
    fees: [{ name: 'Плата за открытие лимита', pct: 0.5 }],
    collateral: 'Без залога',
  },
  {
    code: 'development',
    name: 'Кредит на развитие',
    kind: 'loan',
    suits: 'Оборудование, транспорт, ремонт, открытие новой точки',
    amountMin: 3_000_000,
    amountMax: 30_000_000,
    termMin: 12,
    termMax: 60,
    ratePct: 21,
    fees: [{ name: 'Комиссия за выдачу', pct: 1 }],
    collateral: 'Залог приобретаемого имущества или поручительство',
  },
];

export const productByCode = (c: ProductCode) => PRODUCTS.find((p) => p.code === c)!;

export const GOALS: { id: BusinessGoal; title: string; hint: string; product: ProductCode }[] = [
  { id: 'purchase', title: 'Закупить товар или сырьё', hint: 'Деньги вернутся с продаж закупленного товара', product: 'working_capital' },
  { id: 'cash_gap', title: 'Закрыть кассовый разрыв', hint: 'Клиент заплатит позже, а платить нужно сейчас', product: 'overdraft' },
  { id: 'equipment', title: 'Купить оборудование', hint: 'Станок, печь, транспорт, ремонт', product: 'development' },
  { id: 'gov_contract', title: 'Исполнить госконтракт', hint: 'Закупить материалы под контракт', product: 'working_capital' },
  { id: 'marketplace', title: 'Запасы для маркетплейса', hint: 'Товар к сезону на Ozon, Wildberries', product: 'working_capital' },
];


/** Справочник причин решения: код → формулировка для банка и для клиента */
export const REASON_CATALOG: Record<string, Reason> = {
  HS1: { code: 'HS1', bank: 'HS1 — бизнесу меньше 6 месяцев', plain: 'Бизнес работает меньше полугода — данных для оценки пока мало' },
  HS2: { code: 'HS2', bank: 'HS2 — исполнительные производства > 300 000 ₽', plain: 'Есть крупные исполнительные производства' },
  HS3: { code: 'HS3', bank: `HS3 — недоимка > 50 000 ₽`, plain: 'Есть долг перед налоговой больше 50 000 ₽' },
  HS4: { code: 'HS4', bank: 'HS4 — просрочка 90+ дней за 12 мес', plain: 'За последний год была просрочка по кредиту больше 90 дней' },
  HS5: { code: 'HS5', bank: 'HS5 — подтверждённое совпадение по перечням', plain: 'Заявку нельзя одобрить по требованиям закона' },
  AFFORD: { code: 'REQUESTED_AMOUNT_EXCEEDS_AFFORDABILITY', bank: 'REQUESTED_AMOUNT_EXCEEDS_AFFORDABILITY — DSCR ниже 1,3', plain: 'Сумма больше, чем позволяет ваш денежный поток' },
  TREND: { code: 'REVENUE_TREND_NEGATIVE', bank: 'REVENUE_TREND_NEGATIVE — поступления упали более чем на 15% за 3 мес', plain: 'Поступления на счёт заметно упали за последние 3 месяца' },
  DATA: { code: 'INSUFFICIENT_DATA', bank: 'INSUFFICIENT_DATA — нет отчётности/истории', plain: 'Не хватает данных о бизнесе' },
  OVERDUE: { code: 'CREDIT_HISTORY_OVERDUE', bank: 'CREDIT_HISTORY_OVERDUE — просрочка 30+ дней', plain: 'В кредитной истории была просрочка больше 30 дней' },
  LIMIT: { code: 'ABOVE_AUTO_LIMIT', bank: `ABOVE_AUTO_LIMIT — сумма выше 5 000 000 ₽`, plain: 'Сумма требует рассмотрения сотрудником банка' },
  COMPLIANCE: { code: 'COMPLIANCE_REVIEW', bank: 'COMPLIANCE_REVIEW — возможное совпадение по перечням', plain: 'Нужна дополнительная проверка по требованиям закона' },
  DEBT_LOAD: { code: 'DEBT_LOAD_HIGH', bank: 'DEBT_LOAD_HIGH — долговая нагрузка выше 35%', plain: 'Текущие платежи по кредитам уже большие' },
};
