import { describe, expect, it } from 'vitest';
import type { AppEvent, Application, AppStatus, Decision, Offer, Outcome, ReasonCode } from '../api';
import { adviceFor, appTitle, confirmedFactors, display, eventText, factorTitle, riskCategory, trackState } from './labels';

const OFFER: Offer = {
  product_type: 'term_loan',
  product_code: 'working_capital',
  product_name: 'Оборотный кредит',
  amount_rub: 3_000_000,
  term_months: 12,
  rate_percent: 18,
  monthly_payment_rub: 275_029,
  total_payment_rub: 3_300_348,
  overpayment_rub: 300_348,
};

function app(status: AppStatus, opts: { decision?: Decision; outcome?: Outcome | null; offer?: Offer | null; reasons?: string[]; factors?: ReasonCode[]; bySystem?: boolean } = {}): Application {
  const { decision, outcome = null, offer = null, reasons = [], factors = [], bySystem = false } = opts;
  return {
    application_id: 'x',
    status,
    created_at: '2026-10-25T10:00:00Z',
    updated_at: '2026-10-25T10:00:00Z',
    application: { product_type: 'term_loan', requested_amount_rub: 3_000_000, term_months: 12, purpose: 'working_capital', segment: 'small', submitted_at: '2026-10-25T10:00:00Z' },
    company: {} as Application['company'],
    financials: {} as Application['financials'],
    credit_history: {} as Application['credit_history'],
    scoring_result: decision ? { application_id: 'x', score: 900, pd: 0.03, risk_grade: 'B', reason_codes: factors, model_version: 'v', decision: { decision, reason_codes: reasons, conditions: [] } } : null,
    enriched_data: null,
    explanation: null,
    product_selected_by_system: bySystem,
    outcome,
    offer,
    actions: [],
  };
}

const ev = (event_type: string, payload: Record<string, unknown> | null = null): AppEvent => ({ id: 1, event_type, payload, created_at: '2026-10-25T10:00:00Z' });
const factor = (code: string, feature: string, impact: ReasonCode['impact'], contribution: number): ReasonCode => ({ code, feature, impact, contribution, description: code });

describe('display — разные исходы выглядят по-разному', () => {
  it('одобрено на запрошенных условиях', () => {
    const d = display(app('confirmed', { decision: 'approve', offer: OFFER }), 'Оборотный кредит');
    expect(d.chip).toBe('Одобрено');
    expect(d.text).toContain('18% годовых');
    expect(d.next).toContain('Примите');
  });
  it('банк подобрал продукт сам на ту же сумму — «Подобрали продукт»', () => {
    const d = display(app('different', { decision: 'approve', outcome: 'ALTERNATIVE_PRODUCT', offer: OFFER, bySystem: true }), 'X');
    expect(d.chip).toBe('Подобрали продукт');
    expect(d.kind).toBe('high');
  });
  it('другой продукт на другую сумму — «Подобрали другой продукт»', () => {
    const d = display(app('different', { decision: 'approve_with_conditions', outcome: 'ALTERNATIVE_PRODUCT', offer: { ...OFFER, amount_rub: 1_000_000 } }), 'X');
    expect(d.chip).toBe('Подобрали другой продукт');
  });
  it('встречное предложение — «Предлагаем другие условия» с обеими суммами', () => {
    const d = display(app('different', { decision: 'approve_with_conditions', outcome: 'COUNTER_OFFER', offer: { ...OFFER, amount_rub: 2_000_000 } }), 'X');
    expect(d.chip).toBe('Предлагаем другие условия');
    expect(d.text).toContain('2 000 000');
    expect(d.text).toContain('3 000 000');
  });
  it('ручная проверка — не оффер: ожидание, без призыва принять', () => {
    const d = display(app('different', { decision: 'manual_review', outcome: 'MANUAL_REVIEW' }), 'X');
    expect(d.chip).toBe('Нужна дополнительная проверка');
    expect(d.banner).toBe('wait');
    expect(d.next).not.toContain('Примите');
  });
  it('сбой — предлагаем повторить проверку, а не подавать заново', () => {
    const d = display(app('failed'), 'X');
    expect(d.next).toBe('Повторите проверку.');
    expect(d.text).toContain('заново подавать не нужно');
  });
  it('выдано — номер договора и пометка о модельной выдаче', () => {
    const d = display({ ...app('issued', { offer: OFFER }), contract_number: 'SC-20261026-ABCDEF' }, 'X');
    expect(d.text).toContain('SC-20261026-ABCDEF');
    expect(d.text).toContain('синтетические');
  });
  it('для каждого статуса есть заголовок', () => {
    for (const s of ['pending', 'failed', 'confirmed', 'different', 'declined', 'accepted', 'issued', 'rejected_by_client'] as AppStatus[]) {
      expect(display(app(s), 'X').title).toBeTruthy();
    }
  });
});

describe('appTitle', () => {
  it('нет подходящего продукта — так и пишем, а не «Оборотный кредит»', () => {
    expect(appTitle(app('declined', { decision: 'decline', reasons: ['NO_SUITABLE_PRODUCT'], bySystem: true }), 'Оборотный кредит')).toBe('Продукт не подобран');
  });
  it('иначе — название продукта', () => expect(appTitle(app('confirmed'), 'Оборотный кредит')).toBe('Оборотный кредит'));
});

describe('trackState — этапы из рекомендаций к USERFLOW', () => {
  it('обработка: после обогащения — оценка', () => expect(trackState(app('pending'), [ev('created'), ev('enriched')]).index).toBe(2));
  it('ручная проверка не отмечена как готовое решение', () => {
    const t = trackState(app('different', { outcome: 'MANUAL_REVIEW' }), []);
    expect(t.index).toBe(3);
    expect(t.labels[t.index]).toBe('Решение готово');
  });
  it('оффер — ход клиента на «Предложение принято»', () => {
    const t = trackState(app('confirmed', { offer: OFFER }), []);
    expect(t.labels[t.index]).toBe('Предложение принято');
  });
  it('принято — осталось оформить', () => expect(trackState(app('accepted', { offer: OFFER }), []).index).toBe(5));
  it('выдано — все этапы пройдены', () => expect(trackState(app('issued', { offer: OFFER }), []).index).toBe(6));
  it('отказ — четыре этапа, стоп на решении', () => {
    const t = trackState(app('declined'), []);
    expect(t.labels).toHaveLength(4);
    expect(t.stop).toBe(true);
  });
  it('сбой после повтора считается по последней попытке', () => {
    const t = trackState(app('failed'), [ev('created'), ev('enriched'), ev('failed'), ev('retry_started'), ev('failed')]);
    expect(t.index).toBe(1);
    expect(t.stop).toBe(true);
  });
});

describe('факторы и рекомендации', () => {
  const factors = [
    factor('SOCIAL_FOLLOWERS', 'social_followers', 'negative', 0.95),
    factor('DEBT_BURDEN', 'debt_to_revenue', 'negative', 0.45),
    factor('LIQUIDITY', 'cash_coverage', 'positive', -0.3),
    factor('WEBSITE_VISITS', 'website_visits', 'positive', -0.2),
  ];
  it('факторы, которых нет в заявке, клиенту не показываем', () => {
    expect(confirmedFactors(factors).map((f) => f.code)).toEqual(['DEBT_BURDEN', 'LIQUIDITY']);
  });
  it('рекомендации — по причине решения и по факторам риска', () => {
    const tips = adviceFor(app('declined', { decision: 'decline', reasons: ['HIGH_RISK_SCORE'], factors }));
    expect(tips[0]).toContain('Снизьте долговую нагрузку или запросите меньшую сумму');
    expect(tips.some((t) => t.includes('погасите часть действующих кредитов'))).toBe(true);
    expect(tips.length).toBeLessThanOrEqual(3);
  });
  it('категория риска вместо грейда', () => {
    expect(riskCategory('A').text).toBe('низкий риск');
    expect(riskCategory('C').text).toBe('средний риск');
    expect(riskCategory('E').text).toBe('высокий риск');
  });
});

describe('eventText', () => {
  it('источники обогащения по-русски', () => expect(eventText(ev('enriched', { sources: ['egrul', 'fns', 'bki'] }))).toBe('Получены данные: ЕГРЮЛ, ФНС, БКИ'));
  it('клиенту — без балла, банку — с баллом', () => {
    expect(eventText(ev('scored', { score: 972, risk_grade: 'B' }))).toBe('Оценка риска завершена');
    expect(eventText(ev('scored', { score: 972, risk_grade: 'B' }), true)).toBe('Оценка риска завершена: балл 972, грейд B');
  });
  it('решение с типом результата', () => expect(eventText(ev('status_changed', { status: 'different', outcome: 'COUNTER_OFFER' }))).toBe('Решение: предлагаем другие условия'));
  it('события сделки', () => {
    expect(eventText(ev('offer_accepted', { status: 'accepted' }))).toBe('Предложение принято');
    expect(eventText(ev('issued', { contract_number: 'SC-1' }))).toBe('Кредит оформлен, договор № SC-1');
    expect(eventText(ev('retry_started'))).toBe('Проверка запущена повторно');
    expect(eventText(ev('bank_decision', { decision: 'decline' }))).toBe('Решение банка: отказать');
  });
  it('неизвестное событие — без технического кода', () => expect(eventText(ev('something'))).toBe('Событие по заявке'));
});

describe('factorTitle', () => {
  it('общее описание модели заменяем названием признака', () => expect(factorTitle({ feature: 'social_followers', description: 'Фактор повышает риск' })).toBe('Подписчики в соцсетях'));
  it('понятное описание модели оставляем', () => expect(factorTitle({ feature: 'debt_to_revenue', description: 'Низкая долговая нагрузка' })).toBe('Низкая долговая нагрузка'));
});
