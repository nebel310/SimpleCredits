import type { AppEvent, AppStatus, Application, Decision, LegalForm, Outcome, ProductType, Purpose, ReasonCode, RiskGrade, Segment } from '../api';
import type { PxName } from '../ui/Px';
import { money, months, rate } from './format';

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

/** Решение сотрудника банка по заявке на ручной проверке */
export const BANK_DECISION_NAME: Record<'approve' | 'approve_with_conditions' | 'decline', string> = {
  approve: 'Одобрить на запрошенных условиях',
  approve_with_conditions: 'Одобрить с другой суммой',
  decline: 'Отказать',
};

/** Коды причин решения: правила ML-сервиса (ml/.../scoring/policy.py) и правила каталога на бэкенде */
export const POLICY_REASON: Record<string, string> = {
  CURRENT_PAST_DUE: 'Сейчас есть просрочка по кредитам',
  SEVERE_PAST_DUE_HISTORY: 'За последний год была просрочка 60 дней и больше',
  HIGH_RISK_SCORE: 'Высокий риск по оценке модели',
  RISK_IN_GREY_ZONE: 'Оценка риска в пограничной зоне',
  HIGH_DEBT_SERVICE_RATIO: 'Платежи по долгам — больше 55% месячной выручки',
  LOAN_TO_REVENUE_REDUCTION: 'Запрошенная сумма больше 60% годовой выручки',
  NO_SUITABLE_PRODUCT: 'Под эти условия нет подходящего продукта',
  RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS: 'На рекомендованную сумму нет подходящего продукта',
};

/** Что делать клиенту — по причинам решения. Шаблоны, без выдумок сверх правил */
export const POLICY_ADVICE: Record<string, string> = {
  CURRENT_PAST_DUE: 'Погасите текущую просрочку. Кредитную историю банк берёт из БКИ — в следующей заявке он увидит, что просрочки нет.',
  SEVERE_PAST_DUE_HISTORY: 'Правило смотрит на последние 12 месяцев: когда длительная просрочка выйдет за этот период, заявку можно подать снова.',
  HIGH_RISK_SCORE: 'Снизьте долговую нагрузку или запросите меньшую сумму. Проверьте, что финансы в профиле актуальны.',
  RISK_IN_GREY_ZONE: 'Заявку посмотрит сотрудник банка. Если обороты выросли — обновите финансы в профиле: это учтут в следующей заявке.',
  HIGH_DEBT_SERVICE_RATIO: 'Платежи по долгам съедают больше половины выручки. Помогут досрочное погашение части долгов или меньшая сумма.',
  LOAN_TO_REVENUE_REDUCTION: 'Можно принять предложение на меньшую сумму. Если выручка выросла — обновите её в профиле и подайте новую заявку.',
  NO_SUITABLE_PRODUCT: 'Измените сумму, срок или цель — или выберите продукт в каталоге: там видны все требования.',
  RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS: 'Заявку посмотрит сотрудник банка — он может предложить другую сумму.',
};

/** Что делать клиенту — по факторам модели, которые повышают риск (коды из ml/.../scoring/reasons.py) */
export const FACTOR_ADVICE: Record<string, string> = {
  DEBT_BURDEN: 'Снизьте долговую нагрузку: погасите часть действующих кредитов.',
  DEBT_SERVICE: 'Снизьте ежемесячные платежи по долгам — или запросите сумму меньше.',
  ACTIVE_OBLIGATIONS: 'Закройте часть действующих кредитов перед новой заявкой.',
  CREDIT_UTILIZATION: 'Используйте меньшую долю кредитных лимитов.',
  LOAN_TO_REVENUE: 'Запросите сумму меньше — или обновите выручку в профиле, если обороты выросли.',
  REQUESTED_AMOUNT: 'Попробуйте сумму меньше: посчитайте платёж в калькуляторе ниже.',
  LOAN_TERM: 'Срок короче снижает риск по оценке модели, но увеличивает платёж — посчитайте в калькуляторе.',
  PROFITABILITY: 'Если прибыль в профиле устарела — обновите финансы за последний период.',
  EBITDA_MARGIN: 'Если EBITDA в профиле устарела — обновите финансы за последний период.',
  EXPENSE_RATIO: 'Если расходы в профиле устарели — обновите финансы за последний период.',
  LIQUIDITY: 'Если остаток на счетах вырос — обновите его в профиле.',
  PAST_DUE_HISTORY: 'Платите по кредитам без просрочек — БКИ учитывает последние 12 месяцев.',
  APPLICATION_INTENSITY: 'Много заявок на кредит за полгода снижают оценку — не подавайте их одну за другой.',
};

/** Для этих признаков модель отдаёт только общее «Фактор повышает/снижает риск» */
export const FEATURE_NAME: Record<string, string> = {
  social_followers: 'Подписчики в соцсетях',
  website_visits: 'Посещаемость сайта',
  geo_reviews_count: 'Отзывы на картах',
  log_total_outstanding: 'Остаток долга по кредитам',
};

/** Этих данных нет в заявке: модель подставляет для них значение по умолчанию. Клиенту их не показываем */
export const FEATURE_NOT_IN_APPLICATION = new Set(['social_followers', 'website_visits', 'geo_reviews_count']);

/** Понятное название фактора: описание модели, а если оно общее — название признака */
export function factorTitle(r: { feature: string; description: string }): string {
  return r.description.startsWith('Фактор ') && FEATURE_NAME[r.feature] ? FEATURE_NAME[r.feature] : r.description;
}

/** Что клиент может изменить, чтобы улучшить оценку по этому фактору */
export const FACTOR_ADVICE: Record<string, string> = {
  requested_to_annual_revenue: 'Запросите сумму меньше или подтвердите годовую выручку отчётностью.',
  log_requested_amount: 'Уменьшите запрашиваемую сумму.',
  debt_service_ratio: 'Снизьте платежи по действующим кредитам или запросите меньшую сумму.',
  debt_to_revenue: 'Снизьте общую долговую нагрузку.',
  has_current_past_due: 'Закройте текущую просрочку — следующие заявки будут оцениваться лучше.',
  max_days_past_due_12m: 'Закройте просрочки и поддерживайте платёжную дисциплину.',
  credit_utilization: 'Снизьте загрузку кредитных лимитов.',
  applications_last_6m: 'Не подавайте несколько заявок подряд: частая кредитная активность повышает риск.',
  profitability: 'Подтвердите прибыль отчётностью.',
  ebitda_margin: 'Подтвердите EBITDA и маржинальность отчётностью.',
  cash_coverage: 'Пополните остаток на счёте или подтвердите стабильные поступления.',
  txn_balance_latest: 'Поддерживайте положительный остаток на счёте.',
  expense_ratio: 'Подтвердите структуру расходов или снизьте их долю.',
  log_annual_revenue: 'Подтвердите годовую выручку отчётностью или выпиской.',
  annual_revenue_rub: 'Подтвердите годовую выручку отчётностью или выпиской.',
  tax_debt_rub: 'Погасите налоговую задолженность.',
  unpaid_tax_count: 'Погасите налоговую задолженность.',
  blocked_accounts_count: 'Разблокируйте счета в банке.',
  bki_credit_score: 'Проверьте кредитную историю в БКИ и оспорьте ошибочные записи.',
  company_age_months: 'История компании пока короткая — это ограничение, которое сглаживается со временем.',
};

export function factorAdvice(feature: string): string | null {
  return FACTOR_ADVICE[feature] ?? null;
}

export const CONDITION_NAME: Record<string, string> = { REDUCE_AMOUNT: 'Снизить сумму' };

export type ChipKind = 'high' | 'mid' | 'low' | 'neutral' | 'attention';
export type BannerKind = 'success' | 'wait' | 'action' | 'error' | 'decline';

/** Общая подпись статуса — для статистики. В списках и карточке — display(), с учётом типа результата */
export const STATUS: Record<AppStatus, { chip: string; kind: ChipKind; banner: BannerKind; icon: PxName }> = {
  pending: { chip: 'Обрабатывается', kind: 'mid', banner: 'wait', icon: 'wait' },
  confirmed: { chip: 'Одобрено', kind: 'high', banner: 'success', icon: 'check' },
  different: { chip: 'Другие условия', kind: 'attention', banner: 'action', icon: 'up' },
  declined: { chip: 'Отказ', kind: 'low', banner: 'decline', icon: 'alert' },
  failed: { chip: 'Проверка не завершилась', kind: 'low', banner: 'error', icon: 'alert' },
  accepted: { chip: 'Предложение принято', kind: 'high', banner: 'action', icon: 'doc' },
  issued: { chip: 'Кредит выдан', kind: 'high', banner: 'success', icon: 'gem' },
  rejected_by_client: { chip: 'Клиент отказался', kind: 'neutral', banner: 'decline', icon: 'doc' },
};

export const OUTCOME_NAME: Record<Outcome, string> = {
  ALTERNATIVE_PRODUCT: 'Подобрали другой продукт',
  COUNTER_OFFER: 'Предлагаем другие условия',
  MANUAL_REVIEW: 'Нужна дополнительная проверка',
};

export const GRADE_KIND: Record<RiskGrade, ChipKind> = { A: 'high', B: 'high', C: 'mid', D: 'attention', E: 'low' };

/** Категория риска — то, что видит клиент вместо балла, PD и грейда */
export function riskCategory(g: RiskGrade): { text: string; kind: ChipKind } {
  if (g <= 'B') return { text: 'низкий риск', kind: 'high' };
  if (g === 'C') return { text: 'средний риск', kind: 'mid' };
  return { text: 'высокий риск', kind: 'low' };
}

/**
 * Банк подобрал продукт сам и одобрил его на запрошенную сумму.
 * У старых заявок (до условий предложения) оффера нет — тогда смотрим на решение модели: одобрение без выбора продукта.
 */
export const pickedForClient = (a: Application) =>
  a.offer ? !!a.product_selected_by_system && a.offer.amount_rub === a.application.requested_amount_rub : a.scoring_result?.decision?.decision === 'approve';

/** Под заявку не подошёл ни один продукт */
export const noProduct = (a: Application) => !!a.scoring_result?.decision?.reason_codes.includes('NO_SUITABLE_PRODUCT');

export interface Display {
  chip: string;
  kind: ChipKind;
  banner: BannerKind;
  icon: PxName;
  title: string;
  text: string;
  /** Что делать клиенту сейчас */
  next?: string;
}

const offerTerms = (a: Application) => {
  const o = a.offer;
  return o ? `«${o.product_name}», ${money(o.amount_rub)} на ${months(o.term_months)} под ${rate(o.rate_percent)} годовых` : '';
};

/**
 * Как показать заявку: подпись в списке, баннер карточки, следующее действие.
 * Статус different разбирается по типу результата: другой продукт, другие условия или ручная проверка.
 */
export function display(a: Application, productName: string): Display {
  const st = STATUS[a.status];
  const base = { chip: st.chip, kind: st.kind, banner: st.banner, icon: st.icon };
  const terms = offerTerms(a);
  if (a.offer_outdated) {
    return {
      chip: 'Условия устарели',
      kind: 'attention',
      banner: 'action',
      icon: 'alert',
      title: 'Предложение больше не действует',
      text: 'После этого решения вам оформлен другой кредит — нагрузка изменилась, и прежние условия посчитаны без него. Новая заявка будет оценена с учётом всех кредитов.',
      next: 'Подайте новую заявку с теми же параметрами.',
    };
  }
  switch (a.status) {
    case 'pending':
      return { ...base, title: 'Заявка обрабатывается', text: 'Проверяем компанию в ЕГРЮЛ, ФНС и БКИ и оцениваем риск. Обычно это несколько секунд.', next: 'Ничего делать не нужно — решение появится здесь само.' };
    case 'failed':
      return { ...base, title: 'Проверка не завершилась', text: 'Проверка прервалась из-за технического сбоя. Заявка и данные сохранены — заново подавать не нужно.', next: 'Повторите проверку.' };
    case 'confirmed':
      return a.offer
        ? { ...base, title: 'Заявка одобрена', text: `Одобрено на запрошенных условиях: ${terms}.`, next: 'Примите предложение, чтобы перейти к оформлению.' }
        : { ...base, title: 'Заявка одобрена', text: `${productName}, ${money(a.application.requested_amount_rub)} на ${months(a.application.term_months)} — на запрошенных условиях.` };
    case 'declined': {
      const next = noProduct(a) ? 'Измените параметры заявки и подайте её снова.' : 'Посмотрите, что повлияло на решение и что можно сделать.';
      if (a.bank_decision) return { ...base, title: 'Банк отказал', text: a.bank_decision.comment || 'Решение принял сотрудник банка после проверки.', next };
      if (noProduct(a)) return { ...base, title: 'Нет подходящего продукта', text: a.explanation ?? POLICY_REASON.NO_SUITABLE_PRODUCT, next };
      const why = (a.scoring_result?.decision?.reason_codes ?? []).map((c) => POLICY_REASON[c]).filter(Boolean);
      return { ...base, title: 'Банк отказал', text: why.length ? `Причина: ${why.join('; ').toLowerCase()}.` : 'Причины — ниже.', next };
    }
    case 'accepted':
      return { ...base, title: 'Предложение принято', text: `${terms ? `${terms[0].toUpperCase()}${terms.slice(1)}. ` : ''}Проверьте условия и подтвердите оформление — после этого кредит будет выдан.`, next: 'Подтвердите условия и оформите кредит.' };
    case 'issued':
      return { ...base, title: 'Кредит оформлен', text: `Договор № ${a.contract_number ?? '—'}. Выдача модельная: договор и перевод синтетические, реальных денег и документов нет.` };
    case 'rejected_by_client':
      return { ...base, chip: 'Вы отказались', title: 'Вы отказались от предложения', text: 'Заявка закрыта. Если понадобится финансирование — подайте новую заявку.' };
    case 'different':
      switch (a.outcome) {
        case 'MANUAL_REVIEW':
          return { chip: OUTCOME_NAME.MANUAL_REVIEW, kind: 'mid', banner: 'wait', icon: 'wait', title: 'Нужна дополнительная проверка', text: 'Заявку посмотрит сотрудник банка. Это ещё не предложение — принимать пока нечего.', next: 'Дождитесь решения банка: оно появится в этой заявке.' };
        case 'COUNTER_OFFER':
          return { chip: OUTCOME_NAME.COUNTER_OFFER, kind: 'attention', banner: 'action', icon: 'up', title: 'Предлагаем другие условия', text: a.offer ? `Можем одобрить ${money(a.offer.amount_rub)} вместо ${money(a.application.requested_amount_rub)}: ${terms}.` : (a.explanation ?? ''), next: 'Примите предложение или откажитесь от него.' };
        case 'ALTERNATIVE_PRODUCT':
          if (pickedForClient(a)) {
            const picked = { chip: 'Подобрали продукт', kind: 'high' as ChipKind, banner: 'success' as BannerKind, icon: 'check' as PxName, title: 'Подобрали продукт' };
            return a.offer
              ? { ...picked, text: `Вы не выбирали продукт — банк подобрал подходящий по цели, сумме и сроку: ${terms}.`, next: 'Примите предложение, чтобы перейти к оформлению.' }
              : { ...picked, text: `Вы не выбирали продукт — банк подобрал его сам: ${productName}, ${money(a.application.requested_amount_rub)} на ${months(a.application.term_months)}.` };
          }
          return { chip: OUTCOME_NAME.ALTERNATIVE_PRODUCT, kind: 'attention', banner: 'action', icon: 'up', title: 'Подобрали другой продукт', text: a.offer ? `На запрошенных условиях одобрить не можем. Предлагаем ${terms}.` : (a.explanation ?? ''), next: 'Примите предложение или откажитесь от него.' };
        default:
          return { ...base, title: 'Другие условия', text: a.explanation ?? 'Банк предлагает условия, отличные от запрошенных.' };
      }
  }
}

/** Название заявки: продукт (выбранный клиентом или подобранный банком) */
export const appTitle = (a: Application, productName: string) => (noProduct(a) ? 'Продукт не подобран' : productName);

/** Текст события. Балл и грейд — только для банка */
export function eventText(e: AppEvent, bank = false): string {
  const p = e.payload ?? {};
  switch (e.event_type) {
    case 'created':
      return 'Заявка отправлена';
    case 'enriched': {
      const names: Record<string, string> = { egrul: 'ЕГРЮЛ', fns: 'ФНС', bki: 'БКИ' };
      const src = Array.isArray(p.sources) ? (p.sources as string[]).map((s) => names[s] ?? s).join(', ') : '';
      return src ? `Получены данные: ${src}` : 'Данные из госисточников получены';
    }
    case 'scored':
      return bank && p.score !== undefined ? `Оценка риска завершена: балл ${p.score}, грейд ${p.risk_grade ?? '—'}` : 'Оценка риска завершена';
    case 'status_changed': {
      const st = p.status as AppStatus | undefined;
      const out = p.outcome as Outcome | undefined;
      if (st === 'different' && out && OUTCOME_NAME[out]) return `Решение: ${OUTCOME_NAME[out].toLowerCase()}`;
      return st && STATUS[st] ? `Решение: ${STATUS[st].chip.toLowerCase()}` : 'Статус изменён';
    }
    case 'failed':
      return 'Ошибка обработки';
    case 'manual_decision': {
      const st = p.status as AppStatus | undefined;
      return st === 'confirmed' ? 'Банк одобрил заявку вручную' : st === 'declined' ? 'Банк отклонил заявку вручную' : 'Ручное решение банка';
    }
    default:
      return 'Событие по заявке';
  }
}

/** Цвет точки в истории заявки */
export function eventColor(e: AppEvent): string {
  if (e.event_type === 'failed' || e.event_type === 'offer_rejected') return 'var(--c-negative)';
  if (e.event_type === 'status_changed' || e.event_type === 'bank_decision') {
    const st = e.payload?.status as AppStatus | undefined;
    return st === 'declined' ? 'var(--c-negative)' : st === 'different' ? 'var(--c-attention)' : 'var(--c-high)';
  }
  if (e.event_type === 'issued' || e.event_type === 'offer_accepted') return 'var(--c-high)';
  return 'var(--c-gray)';
}

/** Этапы заявки: обработка (4 этапа) и сделка (ещё 2), как в рекомендациях к USERFLOW */
export const TRACK = ['Заявка отправлена', 'Данные получены', 'Оценка завершена', 'Решение готово', 'Предложение принято', 'Кредит выдан'];

export interface TrackState {
  labels: string[];
  /** Текущий этап; всё, что левее, — пройдено */
  index: number;
  stop?: boolean;
  sub?: string;
}

export function trackState(a: Application, events: AppEvent[]): TrackState {
  const has = (t: string) => events.some((e) => e.event_type === t);
  const processing = () => (has('scored') ? 3 : has('enriched') ? 2 : 1);
  if (a.offer_outdated) return { labels: TRACK, index: a.status === 'accepted' ? 5 : 4, stop: true, sub: 'условия устарели' };
  switch (a.status) {
    case 'pending':
      return { labels: TRACK, index: processing(), sub: 'сейчас' };
    case 'failed': {
      // после повтора этапы считаем по последней попытке
      const last = [...events].reverse();
      const sinceRetry = last.findIndex((e) => e.event_type === 'retry_started');
      const attempt = sinceRetry >= 0 ? events.slice(events.length - sinceRetry) : events;
      const at = attempt.some((e) => e.event_type === 'enriched') ? 2 : 1;
      return { labels: TRACK, index: at, stop: true, sub: 'сбой' };
    }
    case 'declined':
      return { labels: TRACK.slice(0, 4), index: 3, stop: true, sub: 'отказ' };
    case 'different':
      if (a.outcome === 'MANUAL_REVIEW') return { labels: TRACK, index: 3, sub: 'проверяет сотрудник' };
      return a.offer ? { labels: TRACK, index: 4, sub: 'ваш ход' } : { labels: TRACK.slice(0, 4), index: 4 };
    case 'confirmed':
      return a.offer ? { labels: TRACK, index: 4, sub: 'ваш ход' } : { labels: TRACK.slice(0, 4), index: 4 };
    case 'accepted':
      return { labels: TRACK, index: 5, sub: 'подтвердите' };
    case 'issued':
      return { labels: TRACK, index: 6 };
    case 'rejected_by_client':
      return { labels: TRACK, index: 4, stop: true, sub: 'вы отказались' };
  }
}
