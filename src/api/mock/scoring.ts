// Правила оценки для демо: стоп-факторы → баллы 0–100 → категория → матрица «категория × продукт».
// Пороги — демонстрационные, не реальная политика банка.
import type {
  Application,
  ChanceFactor,
  ChancesResult,
  Company,
  HardStop,
  Offer,
  ProductChance,
  ProductCode,
  Recommendation,
  ScoreFactor,
  ScoringResult,
} from '../types';
import { AUTO_LIMIT, PRODUCTS, RULES_VERSION, productByCode, type Profile } from './db';
import { REASON_CATALOG } from '../catalog';

export const DSCR_MIN = 1.3;
export const DSCR_TARGET = 1.5;
export const DEBT_LOAD_MAX = 35;
export const TAX_DEBT_MAX = 50_000;

export const fmt = (n: number) => new Intl.NumberFormat('ru-RU').format(Math.round(n)).replace(/ /g, ' ');

export function annuity(amount: number, ratePct: number, months: number): number {
  const r = ratePct / 100 / 12;
  if (r === 0) return amount / months;
  return (amount * r) / (1 - Math.pow(1 + r, -months));
}

/** Ежемесячная нагрузка: для кредита — аннуитет, для овердрафта — проценты при среднем использовании 50% лимита */
export function monthlyPayment(product: ProductCode, amount: number, months: number): number {
  const p = productByCode(product);
  if (p.kind === 'limit') return (amount * 0.5 * p.ratePct) / 100 / 12;
  return annuity(amount, p.ratePct, months);
}

/** Модельная стоимость использования лимита овердрафта */
export function overdraftCost(used: number, days: number, ratePct = productByCode('overdraft').ratePct) {
  return (used * ratePct * days) / 100 / 365;
}

export function overpayment(product: ProductCode, amount: number, months: number): number {
  const p = productByCode(product);
  if (p.kind === 'limit') return Math.round(overdraftCost(amount * 0.5, months * 30));
  return Math.round(annuity(amount, p.ratePct, months) * months - amount);
}

export function feesFor(product: ProductCode, amount: number) {
  return productByCode(product).fees.map((f) => ({ name: f.name, amount: Math.round(f.amount ?? (amount * (f.pct ?? 0)) / 100) }));
}

/** Максимальная сумма, при которой DSCR не ниже target */
export function maxAmountFor(product: ProductCode, months: number, profile: Profile, target = DSCR_TARGET): number {
  const p = productByCode(product);
  const payMax = profile.cashFlow / target - profile.currentPayments;
  if (payMax <= 0) return 0;
  let amount: number;
  if (p.kind === 'limit') amount = (payMax * 12 * 100) / (0.5 * p.ratePct);
  else {
    const r = p.ratePct / 100 / 12;
    amount = (payMax * (1 - Math.pow(1 + r, -months))) / r;
  }
  return Math.floor(amount / 100_000) * 100_000;
}

const monthsBetween = (fromIso: string, to = new Date()) => {
  const f = new Date(fromIso);
  return (to.getFullYear() - f.getFullYear()) * 12 + (to.getMonth() - f.getMonth());
};

export function ageText(regDate: string) {
  const m = monthsBetween(regDate);
  const y = Math.floor(m / 12);
  const mm = m % 12;
  const yWord = y % 10 === 1 && y % 100 !== 11 ? 'год' : [2, 3, 4].includes(y % 10) && ![12, 13, 14].includes(y % 100) ? 'года' : 'лет';
  if (y === 0) return `${mm} мес`;
  return mm ? `${y} ${yWord} ${mm} мес` : `${y} ${yWord}`;
}

export const REASONS = REASON_CATALOG;

interface ScoreInput {
  app: Pick<Application, 'product' | 'amount' | 'termMonths' | 'finance' | 'round'>;
  company: Company;
  profile: Profile;
  statementAccepted: boolean;
  bkiOk: boolean;
  complianceOpen: boolean;
  complianceConfirmed: boolean;
}

export function effectiveProfile(profile: Profile, statementAccepted: boolean): Profile {
  if (statementAccepted && profile.statement) {
    return { ...profile, trendPct: profile.statement.trendPct, weakMonths: profile.statement.weakMonths, cashFlow: profile.statement.cashFlow };
  }
  return profile;
}

export function computeScoring(input: ScoreInput, id: string): ScoringResult {
  const { app, company } = input;
  const profile = effectiveProfile(input.profile, input.statementAccepted);
  const ageM = monthsBetween(company.regDate);
  const pay = monthlyPayment(app.product, app.amount, app.termMonths);
  const dscr = profile.cashFlow / (profile.currentPayments + pay);
  const debtLoad = ((profile.currentPayments + pay) / profile.inflowsAvg) * 100;

  const hardStops: HardStop[] = [
    { code: 'HS1', text: 'Бизнесу меньше 6 месяцев', plain: REASONS.HS1.plain, triggered: ageM < 6 },
    { code: 'HS2', text: 'Исполнительные производства > 300 000 ₽', plain: REASONS.HS2.plain, triggered: profile.fsspSum > 300_000 },
    { code: 'HS3', text: `Недоимка > ${fmt(TAX_DEBT_MAX)} ₽`, plain: REASONS.HS3.plain, triggered: profile.taxDebt > TAX_DEBT_MAX },
    { code: 'HS4', text: 'Просрочка 90+ дней за 12 мес', plain: REASONS.HS4.plain, triggered: input.bkiOk && profile.overdueMaxDays > 90 },
    { code: 'HS5', text: 'Подтверждённое совпадение по перечням', plain: REASONS.HS5.plain, triggered: input.complianceConfirmed },
  ];

  const m = profile.cashFlow / profile.inflowsAvg;
  const cfPts = m >= 0.25 ? 25 : m >= 0.15 ? 20 : m >= 0.1 ? 16 : m >= 0.05 ? 10 : 4;
  const od = profile.overdueMaxDays;
  const discPts = !input.bkiOk ? 0 : od === 0 ? 20 : od <= 30 ? 14 : od <= 60 ? 10 : od <= 90 ? 5 : 0;
  const curLoad = profile.cashFlow ? profile.currentPayments / profile.cashFlow : 1;
  const loadPts = curLoad === 0 ? 12 : curLoad <= 0.15 ? 10 : curLoad <= 0.3 ? 7 : curLoad <= 0.5 ? 4 : 0;
  const wm = profile.weakMonths;
  const stabPts = wm === 0 ? 12 : wm === 1 ? 10 : wm === 2 ? 8 : wm === 3 ? 6 : wm <= 5 ? 3 : 0;
  const ageY = ageM / 12;
  const agePts = ageY >= 5 ? 10 : ageY >= 4 ? 9 : ageY >= 3 ? 8 : ageY >= 2 ? 6 : ageY >= 1 ? 4 : 1;
  const bankPts = profile.bankYears >= 3 ? 6 : profile.bankYears >= 2 ? 4 : profile.bankYears >= 1 ? 3 : 1;
  const taxPts = profile.taxDebt > 0 ? 0 : profile.arbitrDefendant === 0 ? 5 : profile.arbitrDefendant === 1 ? 3 : 1;
  const indPts = profile.okvedRisk === 'low' ? 5 : profile.okvedRisk === 'mid' ? 3 : 1;
  const g = app.finance.guarantor;
  const colPts = app.product === 'development' ? 5 : g === 'third_party' ? 4 : g === 'owner' ? 3 : 0;

  const factors: ScoreFactor[] = [
    { key: 'cash', name: 'Денежный поток', value: `${fmt(profile.cashFlow)} ₽/мес${profile.trendPct < 0 ? `, поступления ${profile.trendPct}% за 3 мес` : ''}`, points: cfPts, max: 25, plain: 'Сколько денег остаётся у бизнеса каждый месяц' },
    { key: 'disc', name: 'Кредитная дисциплина', value: input.bkiOk ? profile.overdueNote : 'нет ответа БКИ', points: discPts, max: 20, plain: 'Как вы платили по кредитам раньше' },
    { key: 'load', name: 'Долговая нагрузка сейчас', value: `платежи ${fmt(profile.currentPayments)} ₽/мес · ${(curLoad * 100).toFixed(1).replace('.', ',')}% потока`, points: loadPts, max: 12, plain: 'Какую часть денег уже съедают кредиты' },
    { key: 'stab', name: 'Стабильность поступлений', value: `${wm} слабых мес. из 12`, points: stabPts, max: 12, plain: 'Насколько ровно деньги приходят на счёт' },
    { key: 'age', name: 'Возраст бизнеса', value: ageText(company.regDate), points: agePts, max: 10, plain: 'Сколько лет работает бизнес' },
    { key: 'bank', name: 'Отношения с банком', value: profile.bankYears ? `счёт ${profile.bankYears} г.` : 'счёт открыт недавно', points: bankPts, max: 6, plain: 'Как давно у вас счёт в банке' },
    { key: 'tax', name: 'Налоги и суды', value: profile.taxDebt ? `недоимка ${fmt(profile.taxDebt)} ₽` : profile.arbitrNote, points: taxPts, max: 5, plain: 'Долги перед налоговой и суды' },
    { key: 'ind', name: 'Отрасль', value: `${company.okved} · ${company.okvedName}`, points: indPts, max: 5, plain: 'Насколько стабильна ваша отрасль' },
    { key: 'col', name: 'Обеспечение', value: app.product === 'development' ? 'залог имущества' : g === 'none' ? 'нет' : g === 'owner' ? 'поручительство владельца' : 'поручительство третьего лица', points: colPts, max: 5, plain: 'Залог или поручитель' },
  ];

  const score = factors.reduce((s, f) => s + f.points, 0);
  const anyStop = hardStops.some((h) => h.triggered);
  let category: ScoringResult['category'] = score >= 80 ? 'A' : score >= 70 ? 'B' : score >= 50 ? 'C' : score >= 35 ? 'D' : 'E';
  if (anyStop) category = 'E';

  const reasonCodes: string[] = [];
  let outcome: ScoringResult['recommendation']['outcome'];
  const recAmount = maxAmountFor(app.product, app.termMonths, profile);
  const insufficient = input.profile.revenueYear === null || ageM < 6;

  if (anyStop && !(insufficient && hardStops.filter((h) => h.triggered).every((h) => h.code === 'HS1'))) {
    outcome = 'DECLINE';
    hardStops.filter((h) => h.triggered).forEach((h) => reasonCodes.push(h.code));
  } else if (insufficient && !input.statementAccepted) {
    outcome = 'REQUEST_DOCS';
    reasonCodes.push('DATA');
  } else if (input.complianceOpen) {
    outcome = 'MANUAL_REVIEW';
    reasonCodes.push('COMPLIANCE');
  } else if (profile.trendPct <= -15 && !input.statementAccepted) {
    outcome = 'REQUEST_DOCS';
    reasonCodes.push('TREND');
  } else if (app.amount > AUTO_LIMIT) {
    outcome = 'MANUAL_REVIEW';
    reasonCodes.push('LIMIT');
    if (dscr < DSCR_MIN) reasonCodes.push('AFFORD');
  } else if (category === 'A' || category === 'B') {
    if (dscr >= DSCR_MIN) outcome = 'APPROVE';
    else if (recAmount >= productByCode(app.product).amountMin) {
      outcome = 'COUNTER_OFFER';
      reasonCodes.push('AFFORD');
    } else {
      outcome = 'MANUAL_REVIEW';
      reasonCodes.push('AFFORD');
    }
  } else {
    outcome = 'MANUAL_REVIEW';
    if (dscr < DSCR_MIN) reasonCodes.push('AFFORD');
    if (input.bkiOk && profile.overdueMaxDays > 30) reasonCodes.push('OVERDUE');
    if (debtLoad > DEBT_LOAD_MAX) reasonCodes.push('DEBT_LOAD');
  }

  const recommendation: ScoringResult['recommendation'] = { outcome, reasonCodes };
  if (dscr < DSCR_MIN && recAmount > 0) {
    recommendation.amount = Math.min(recAmount, app.amount);
    recommendation.termMonths = app.termMonths;
    recommendation.dscrAtAmount = profile.cashFlow / (profile.currentPayments + monthlyPayment(app.product, recommendation.amount, app.termMonths));
  }

  return {
    id,
    round: app.round,
    at: new Date().toISOString(),
    rulesVersion: RULES_VERSION,
    score,
    category,
    hardStops,
    factors,
    dscr,
    debtLoadPct: debtLoad,
    monthlyPayment: pay,
    cashFlow: profile.cashFlow,
    currentPayments: profile.currentPayments,
    recommendation,
  };
}

export function makeOffer(params: {
  id: string;
  version: number;
  kind: Offer['kind'];
  product: ProductCode;
  amount: number;
  termMonths: number;
  requested: Offer['requested'];
  guarantor: string;
  validDays?: number;
}): Offer {
  const p = productByCode(params.product);
  const valid = new Date(Date.now() + (params.validDays ?? 5) * 86400_000);
  return {
    id: params.id,
    version: params.version,
    kind: params.kind,
    product: params.product,
    amount: params.amount,
    termMonths: params.termMonths,
    ratePct: p.ratePct,
    monthlyPayment: p.kind === 'limit' ? 0 : Math.round(annuity(params.amount, p.ratePct, params.termMonths)),
    overpayment: overpayment(params.product, params.amount, params.termMonths),
    fees: feesFor(params.product, params.amount),
    collateral: p.collateral,
    guarantor: params.guarantor,
    validUntil: valid.toISOString(),
    requested: params.requested,
  };
}

const sigmoidPct = (score: number) => Math.round(100 / (1 + Math.exp(-(score - 55) / 8)));

/** Предварительная оценка шансов на главной (до заявки) */
export function computeChances(company: Company, profile: Profile, bkiConsent: boolean, now: string): ChancesResult {
  const ageM = monthsBetween(company.regDate);
  const insufficient = profile.revenueYear === null || ageM < 6;
  const asOf = now;
  const factors: ChanceFactor[] = [];

  factors.push({ key: 'inflows', dir: profile.trendPct < -10 ? '-' : '+', name: 'Обороты по счёту', note: profile.trendPct < -10 ? `упали на ${Math.abs(profile.trendPct)}% за 3 месяца` : profile.trendPct > 0 ? `растут, +${profile.trendPct}% за 3 месяца` : 'стабильные', source: 'Выписка по вашему счёту', asOf });
  factors.push({ key: 'revenue', dir: profile.revenueYear ? '+' : '?', name: 'Выручка за год', note: profile.revenueYear ? `${fmt(profile.revenueYear)} ₽` : 'отчётности ещё нет', source: `ФНС, ${profile.revenueAsOf}`, asOf });
  factors.push({ key: 'age', dir: ageM >= 24 ? '+' : ageM >= 6 ? '?' : '-', name: 'Возраст бизнеса', note: ageText(company.regDate), source: 'ЕГРЮЛ/ЕГРИП', asOf });
  factors.push({ key: 'tax', dir: profile.taxDebt > 0 ? '-' : '+', name: 'Налоги', note: profile.taxDebt > 0 ? `долг ${fmt(profile.taxDebt)} ₽` : 'долгов нет', source: 'ФНС', asOf });
  if (bkiConsent) {
    factors.push({ key: 'bki', dir: profile.overdueMaxDays > 30 ? '-' : profile.overdueMaxDays > 0 ? '?' : '+', name: 'Кредитная история', note: profile.overdueNote, source: 'БКИ', asOf });
    const load = profile.cashFlow ? (profile.currentPayments / profile.cashFlow) * 100 : 0;
    factors.push({ key: 'load', dir: load > 35 ? '-' : '+', name: 'Долговая нагрузка', note: `${load.toFixed(1).replace('.', ',')}% денежного потока`, source: 'БКИ и выписка', asOf });
  } else {
    factors.push({ key: 'bki', dir: '?', name: 'Кредитная история', note: 'ещё не проверена — нужно ваше согласие', source: 'БКИ', asOf: undefined });
    factors.push({ key: 'load', dir: '?', name: 'Долговая нагрузка', note: 'посчитаем после проверки истории', source: 'БКИ и выписка', asOf: undefined });
  }
  factors.push({ key: 'courts', dir: profile.arbitrDefendant > 0 ? '-' : '+', name: 'Суды', note: profile.arbitrNote, source: 'Картотека арбитражных дел', asOf });

  const products: ProductChance[] = PRODUCTS.map((p) => {
    const term = p.code === 'development' ? 36 : p.code === 'overdraft' ? 12 : 12;
    if (insufficient) {
      return { product: p.code, level: 'unknown', pct: null, approx: false, limit: null, fits: false, blocker: 'Не хватает данных: нет отчётности и короткая история оборотов' };
    }
    const limit = Math.min(p.amountMax, maxAmountFor(p.code, term, profile));
    const stops: string[] = [];
    if (profile.taxDebt > TAX_DEBT_MAX) stops.push(`долг перед налоговой ${fmt(profile.taxDebt)} ₽`);
    if (bkiConsent && profile.overdueMaxDays > 90) stops.push('просрочка больше 90 дней за год');
    if (stops.length) return { product: p.code, level: 'blocked', pct: null, approx: false, limit: null, fits: false, blocker: `Стоп-фактор: ${stops.join(', ')}` };
    const amount = Math.max(p.amountMin, Math.min(limit, p.amountMax));
    const sc = computeScoring(
      {
        app: { product: p.code, amount, termMonths: term, round: 1, finance: { guarantor: 'none' } as Application['finance'] },
        company,
        profile,
        statementAccepted: false,
        bkiOk: bkiConsent,
        complianceOpen: false,
        complianceConfirmed: false,
      },
      'pre',
    );
    let adj = 0;
    if (p.code === 'overdraft') adj += profile.bankYears >= 1 ? 6 : -10;
    if (p.code === 'development') adj += (ageM < 36 ? -12 : 0) + (profile.trendPct < -10 ? -10 : 0);
    if (!bkiConsent) adj += 4; // без БКИ дисциплина не учтена — частично компенсируем средним значением
    let pct = Math.max(3, Math.min(95, sigmoidPct(sc.score + adj)));
    if (limit < p.amountMin) pct = Math.min(pct, 20);
    const level: ProductChance['level'] = pct >= 65 ? 'high' : pct >= 40 ? 'mid' : 'low';
    return { product: p.code, level, pct, approx: !bkiConsent, limit: limit >= p.amountMin ? limit : null, fits: level !== 'low' };
  });

  const recommendations: Recommendation[] = [];
  if (!bkiConsent && !insufficient) {
    recommendations.push({ id: 'consent', title: 'Разрешите проверить кредитную историю', text: 'Пока шансы посчитаны без бюро кредитных историй. С согласием оценка станет точнее. Согласие можно отозвать.', effect: 'Поможет уточнить оценку', action: { label: 'Проверить кредитную историю', kind: 'consent' } });
  }
  if (insufficient) {
    recommendations.push({ id: 'statement', title: 'Загрузите выписку за все месяцы работы', text: 'Отчётности в ФНС ещё нет. Выписка по счетам покажет обороты — по ним банк сможет посчитать условия.', effect: 'Поможет уточнить оценку', action: { label: 'Подать заявку с выпиской', kind: 'apply', product: 'overdraft' } });
    recommendations.push({ id: 'wait', title: 'Вернитесь, когда бизнесу будет 6 месяцев', text: 'Тогда появятся данные для автоматической оценки.', effect: 'Учитывается в оценке' });
  }
  if (profile.taxDebt > 0) {
    recommendations.push({ id: 'tax', title: `Погасите долг перед налоговой ${fmt(profile.taxDebt)} ₽`, text: 'Пока есть долг больше 50 000 ₽, по правилам банк не выдаёт кредит. Данные ФНС обновляются в течение нескольких дней после оплаты.', effect: 'Снимет стоп-фактор по правилам', action: { label: 'Как погасить', kind: 'link' } });
  }
  if (bkiConsent && profile.overdueMaxDays > 30) {
    recommendations.push({ id: 'overdue', title: 'Платите текущие кредиты без просрочек', text: `В истории: ${profile.overdueNote}. Чем больше времени прошло без просрочек, тем лучше оценка.`, effect: 'Учитывается в оценке' });
  }
  if (profile.trendPct < -10) {
    recommendations.push({ id: 'trend', title: 'Покажите обороты в других банках', text: 'Если часть денег приходит на счёт в другом банке, приложите выписку к заявке.', effect: 'Поможет уточнить оценку', action: { label: 'Подать заявку с выпиской', kind: 'apply', product: 'working_capital' } });
  }
  if (!insufficient && profile.taxDebt === 0) {
    const best = [...products].filter((x) => x.pct !== null).sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))[0];
    if (best) recommendations.push({ id: 'apply', title: `Подайте заявку: ${productByCode(best.product).name.toLowerCase()}`, text: 'Сумму и срок подставим из оценки — их можно поменять.', effect: 'Предварительно подходит', action: { label: 'Начать заявку', kind: 'apply', product: best.product } });
  }

  return {
    state: insufficient ? 'insufficient' : 'ready',
    calibrated: true,
    bkiConsent,
    calculatedAt: now,
    products,
    factors,
    recommendations,
  };
}
