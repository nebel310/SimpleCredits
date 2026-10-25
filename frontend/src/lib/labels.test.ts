import { describe, expect, it } from 'vitest';
import type { AppEvent, Application, AppStatus, Decision } from '../api';
import { eventText, factorTitle, outcomeText, trackIndex } from './labels';

function app(status: AppStatus, decision?: Decision, conditions: { code: string; description: string; recommended_amount_rub: number }[] = []): Application {
  return {
    application_id: 'x',
    status,
    created_at: '2026-10-25T10:00:00Z',
    updated_at: '2026-10-25T10:00:00Z',
    application: { product_type: 'term_loan', requested_amount_rub: 3_000_000, term_months: 12, purpose: 'working_capital', segment: 'small', submitted_at: '2026-10-25T10:00:00Z' },
    company: {} as Application['company'],
    financials: {} as Application['financials'],
    credit_history: {} as Application['credit_history'],
    scoring_result: decision ? { application_id: 'x', score: 900, pd: 0.03, risk_grade: 'B', reason_codes: [], model_version: 'v', decision: { decision, reason_codes: [], conditions } } : null,
    enriched_data: null,
    explanation: null,
  };
}

const ev = (event_type: string, payload: Record<string, unknown> | null = null): AppEvent => ({ id: 1, event_type, payload, created_at: '2026-10-25T10:00:00Z' });

describe('outcomeText — заголовок для каждого исхода из USERFLOW §5', () => {
  it('confirmed', () => expect(outcomeText(app('confirmed', 'approve'), 'Оборотный кредит').title).toBe('Заявка одобрена'));
  it('different + approve_with_conditions', () => expect(outcomeText(app('different', 'approve_with_conditions'), 'X').title).toBe('Можем одобрить на других условиях'));
  it('different + manual_review', () => expect(outcomeText(app('different', 'manual_review'), 'X').title).toBe('Автоматического решения нет'));
  it('different + approve (продукт не выбран)', () => {
    const t = outcomeText(app('different', 'approve'), 'Оборотный кредит');
    expect(t.title).toBe('Одобрено — продукт подобрали за вас');
    expect(t.text).toContain('Оборотный кредит');
  });
  it('declined', () => expect(outcomeText(app('declined', 'decline'), 'X').title).toBe('Банк отказал'));
  it('failed', () => expect(outcomeText(app('failed'), 'X').title).toBe('Не удалось получить решение'));
  it('pending', () => expect(outcomeText(app('pending'), 'X').title).toBe('Заявка обрабатывается'));
});

describe('trackIndex — этап трекера по событиям', () => {
  it('pending без событий — на первом шаге', () => expect(trackIndex('pending', [ev('created')])).toBe(1));
  it('pending после обогащения — скоринг', () => expect(trackIndex('pending', [ev('created'), ev('enriched')])).toBe(2));
  it('решение принято — все этапы пройдены', () => expect(trackIndex('confirmed', [])).toBe(4));
  it('отказ — останавливаемся на «Решение»', () => expect(trackIndex('declined', [])).toBe(3));
  it('ошибка до скоринга — останавливаемся на «Скоринг»', () => expect(trackIndex('failed', [ev('created'), ev('enriched')])).toBe(2));
});

describe('eventText', () => {
  it('источники обогащения по-русски', () => expect(eventText(ev('enriched', { sources: ['egrul', 'fns', 'bki'] }))).toBe('Получены данные: ЕГРЮЛ, ФНС, БКИ'));
  it('скоринг с баллом и грейдом', () => expect(eventText(ev('scored', { score: 972, risk_grade: 'B' }))).toBe('Скоринг готов: балл 972, грейд B'));
  it('смена статуса', () => expect(eventText(ev('status_changed', { status: 'confirmed' }))).toBe('Статус: одобрено'));
  it('неизвестное событие — как есть', () => expect(eventText(ev('something'))).toBe('something'));
});

describe('factorTitle', () => {
  it('общее описание модели заменяем названием признака', () => expect(factorTitle({ feature: 'social_followers', description: 'Фактор повышает риск' })).toBe('Подписчики в соцсетях'));
  it('понятное описание модели оставляем', () => expect(factorTitle({ feature: 'debt_to_revenue', description: 'Низкая долговая нагрузка' })).toBe('Низкая долговая нагрузка'));
});
