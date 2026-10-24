import type { AppEvent, AppStatus, Application, Decision, LegalForm, ProductType, Purpose, RiskGrade, Segment } from '../api';
import type { PxName } from '../ui/Px';
import { money } from './format';

// Подписи для значений из API. Названия продуктов берутся из каталога GET /products, здесь — запасные.

export const PRODUCT_TYPE_NAME: Record<ProductType, string> = {
  microloan: 'Микрозайм',
  term_loan: 'Оборотный кредит',
  overdraft: 'Овердрафт',
  credit_line: 'Кредитная линия',
  leasing: 'Лизинг оборудования',
};

export const PURPOSE_NAME: Record<Purpose, string> = {
  working_capital: 'Пополнить оборотные средства',
  equipment: 'Купить оборудование',
  expansion: 'Развитие бизнеса',
  refinancing: 'Рефинансировать долги',
  other: 'Другое',
};

export const SEGMENT_NAME: Record<Segment, string> = { micro: 'Микробизнес', small: 'Малый бизнес' };
export const LEGAL_FORM_NAME: Record<LegalForm, string> = { llc: 'ООО', individual_entrepreneur: 'ИП', joint_stock_company: 'АО' };

export const DECISION_NAME: Record<Decision, string> = {
  approve: 'Одобрить',
  approve_with_conditions: 'Одобрить с условиями',
  manual_review: 'Ручная проверка',
  decline: 'Отказать',
};

/** Коды политики ML-сервиса (ml/src/simplecredits/ml/scoring/policy.py) */
export const POLICY_REASON: Record<string, string> = {
  CURRENT_PAST_DUE: 'Сейчас есть просрочка по кредитам',
  SEVERE_PAST_DUE_HISTORY: 'За последний год была просрочка 60 дней и больше',
  HIGH_RISK_SCORE: 'Высокая вероятность дефолта по оценке модели',
  RISK_IN_GREY_ZONE: 'Оценка риска в пограничной зоне',
  HIGH_DEBT_SERVICE_RATIO: 'Платежи по долгам — больше 55% месячной выручки',
  LOAN_TO_REVENUE_REDUCTION: 'Запрошенная сумма больше 60% годовой выручки',
};

export const CONDITION_NAME: Record<string, string> = { REDUCE_AMOUNT: 'Снизить сумму' };

export type ChipKind = 'high' | 'mid' | 'low' | 'neutral' | 'attention';
export type BannerKind = 'success' | 'wait' | 'action' | 'error' | 'decline';

export const STATUS: Record<AppStatus, { chip: string; kind: ChipKind; banner: BannerKind; icon: PxName }> = {
  pending: { chip: 'Обрабатывается', kind: 'mid', banner: 'wait', icon: 'wait' },
  confirmed: { chip: 'Одобрено', kind: 'high', banner: 'success', icon: 'check' },
  different: { chip: 'Другие условия', kind: 'attention', banner: 'action', icon: 'up' },
  declined: { chip: 'Отказ', kind: 'low', banner: 'decline', icon: 'alert' },
  failed: { chip: 'Ошибка обработки', kind: 'low', banner: 'error', icon: 'alert' },
};

export const GRADE_KIND: Record<RiskGrade, ChipKind> = { A: 'high', B: 'high', C: 'mid', D: 'attention', E: 'low' };

/** Что сказать клиенту по итогу заявки: заголовок и пояснение */
export function outcomeText(a: Application, productName: string): { title: string; text: string } {
  const d = a.scoring_result?.decision?.decision;
  switch (a.status) {
    case 'pending':
      return { title: 'Заявка обрабатывается', text: 'Проверяем данные в ЕГРЮЛ, ФНС и БКИ и считаем скоринг. Обычно это несколько секунд.' };
    case 'confirmed':
      return { title: 'Заявка одобрена', text: `${productName} на ${money(a.application.requested_amount_rub)} на ${a.application.term_months} мес — на тех условиях, которые вы запросили.` };
    case 'declined':
      return { title: 'Банк отказал', text: 'Причины — ниже. Посмотрите факторы, которые сильнее всего повлияли на оценку.' };
    case 'failed':
      return { title: 'Не удалось получить решение', text: 'Сервис скоринга не ответил. Данные заявки сохранены — подайте заявку ещё раз чуть позже.' };
    case 'different':
      if (d === 'approve_with_conditions') return { title: 'Можем одобрить на других условиях', text: 'Модель одобряет заявку, но с условием — оно указано ниже.' };
      if (d === 'manual_review') return { title: 'Автоматического решения нет', text: 'Модель отнесла заявку к пограничной зоне риска: такую заявку нужно смотреть вручную. Ниже — что повлияло на оценку.' };
      return { title: 'Одобрено — продукт подобрали за вас', text: `Вы не выбирали продукт, поэтому банк подобрал его сам: ${productName}, ${money(a.application.requested_amount_rub)} на ${a.application.term_months} мес.` };
  }
}

export function eventText(e: AppEvent): string {
  const p = e.payload ?? {};
  switch (e.event_type) {
    case 'created':
      return 'Заявка создана';
    case 'enriched': {
      const names: Record<string, string> = { egrul: 'ЕГРЮЛ', fns: 'ФНС', bki: 'БКИ' };
      const src = Array.isArray(p.sources) ? (p.sources as string[]).map((s) => names[s] ?? s).join(', ') : '';
      return src ? `Получены данные: ${src}` : 'Данные из госисточников получены';
    }
    case 'scored':
      return `Скоринг готов: балл ${p.score ?? '—'}, грейд ${p.risk_grade ?? '—'}`;
    case 'status_changed': {
      const st = p.status as AppStatus | undefined;
      return st && STATUS[st] ? `Статус: ${STATUS[st].chip.toLowerCase()}` : 'Статус изменён';
    }
    case 'failed':
      return 'Ошибка обработки';
    default:
      return e.event_type;
  }
}

/** Этапы обработки заявки для трекера: создана → госисточники → скоринг → решение */
export const TRACK = ['Заявка создана', 'ЕГРЮЛ, ФНС, БКИ', 'Скоринг', 'Решение'];

export function trackIndex(status: AppStatus, events: AppEvent[]): number {
  if (status === 'failed') return events.some((e) => e.event_type === 'scored') ? 3 : events.some((e) => e.event_type === 'enriched') ? 2 : 1;
  if (status === 'declined') return 3;
  if (status !== 'pending') return 4;
  if (events.some((e) => e.event_type === 'scored')) return 3;
  if (events.some((e) => e.event_type === 'enriched')) return 2;
  return 1;
}
