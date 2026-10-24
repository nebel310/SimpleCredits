import type { AppStatus, ApplicationView, ProductCode, Role, TaskType } from '../api';

export const PRODUCT_NAME: Record<ProductCode, string> = {
  working_capital: 'Оборотный кредит',
  overdraft: 'Овердрафт',
  development: 'Кредит на развитие',
};

export const ROLE_NAME: Record<Role, string> = {
  owner: 'Владелец',
  accountant: 'Бухгалтер',
  viewer: 'Наблюдатель',
  manager: 'Кредитный менеджер',
  underwriter: 'Андеррайтер',
  compliance: 'Комплаенс',
};

export const TRACK = ['Отправлена', 'Проверка данных', 'Оценка', 'Решение', 'Подписание', 'Выдача'];

export function trackIndex(st: AppStatus): number {
  switch (st) {
    case 'DRAFT':
    case 'SUBMITTED':
      return 0;
    case 'CHECKS':
    case 'WAITING_SOURCE':
    case 'DOCS_REQUESTED':
    case 'DOCS_REVIEW':
      return 1;
    case 'SCORING':
    case 'MANUAL_REVIEW':
      return 2;
    case 'OFFER':
    case 'DECLINED':
    case 'OFFER_REJECTED':
    case 'EXPIRED':
      return 3;
    case 'SIGNING':
      return 4;
    case 'DISBURSEMENT':
      return 5;
    case 'ACTIVE':
    case 'REPAID':
      return 6;
    case 'CANCELLED':
      return 0;
  }
}

export type BannerKind = 'wait' | 'success' | 'action' | 'error' | 'decline' | 'dark';

export interface StatusMeta {
  chip: string;
  chipClass: 'high' | 'mid' | 'low' | 'neutral' | 'dark' | 'lime' | 'attention';
  title: string;
  what: string;
  who: string;
  you: string;
  banner: BannerKind;
}

export function statusMeta(app: Pick<ApplicationView, 'status' | 'waitingFor' | 'offer' | 'disbursement' | 'signing' | 'committee'>): StatusMeta {
  switch (app.status) {
    case 'DRAFT':
      return { chip: 'Черновик', chipClass: 'neutral', title: 'Заявка ещё не отправлена', what: 'Черновик сохраняется сам', who: 'Вы', you: 'Заполните шаги и отправьте', banner: 'action' };
    case 'SUBMITTED':
      return { chip: 'Отправлена', chipClass: 'mid', title: 'Заявка отправлена', what: 'Скоро начнётся проверка данных', who: 'Система банка', you: 'Ничего не нужно делать', banner: 'wait' };
    case 'CHECKS':
      return { chip: 'Проверка данных', chipClass: 'mid', title: 'Проверяем данные', what: 'Запрашиваем реестр, налоги, кредитную историю, суды и приставов', who: 'Система банка', you: 'Ничего не нужно делать — статус обновится здесь', banner: 'wait' };
    case 'WAITING_SOURCE':
      return { chip: 'Ждём источник', chipClass: 'mid', title: 'Ждём ответ внешнего источника. Это не отказ', what: 'Один из источников не ответил вовремя — банк повторит запрос сам', who: 'Система банка', you: 'Ничего не нужно делать', banner: 'wait' };
    case 'SCORING':
      return { chip: 'Оценка', chipClass: 'mid', title: 'Считаем оценку', what: 'Банк считает оценку по правилам', who: 'Система банка', you: 'Ничего не нужно делать', banner: 'wait' };
    case 'MANUAL_REVIEW':
      return { chip: 'Дополнительная проверка', chipClass: 'mid', title: app.committee ? 'Заявку рассматривает кредитный комитет' : 'Дополнительная проверка. Это не отказ', what: app.committee ? 'Сумма требует коллегиального решения' : 'Заявку смотрит сотрудник банка', who: app.committee ? 'Кредитный комитет' : 'Сотрудник банка', you: 'Ничего не нужно делать. Если понадобятся документы — придёт запрос', banner: 'wait' };
    case 'DOCS_REQUESTED':
      return { chip: 'Нужен документ', chipClass: 'attention', title: 'Банк просит документ. Это не отказ', what: 'После проверки документа рассмотрение продолжится', who: 'Вы', you: 'Загрузите документ', banner: 'action' };
    case 'DOCS_REVIEW':
      return { chip: 'Документы на проверке', chipClass: 'mid', title: 'Документы на проверке', what: 'Менеджер проверяет документы', who: 'Кредитный менеджер', you: 'Ничего не нужно делать', banner: 'wait' };
    case 'OFFER':
      return { chip: app.offer?.kind === 'counter' ? 'Другие условия' : 'Одобрено', chipClass: app.offer?.kind === 'counter' ? 'mid' : 'high', title: app.offer?.kind === 'counter' ? 'Банк предлагает другие условия' : 'Банк одобрил заявку', what: 'Решение готово', who: 'Вы', you: 'Посмотрите условия и примите предложение', banner: 'action' };
    case 'SIGNING':
      return { chip: app.signing?.status === 'error' ? 'Ошибка подписи' : 'Подписание', chipClass: app.signing?.status === 'error' ? 'low' : 'mid', title: app.signing?.status === 'error' ? 'Подпись не прошла' : 'Осталось подписать договор', what: 'Условия приняты', who: 'Владелец', you: 'Подпишите договор', banner: app.signing?.status === 'error' ? 'error' : 'action' };
    case 'DISBURSEMENT':
      return { chip: app.disbursement?.status === 'checking' ? 'Проверяем операцию' : 'Готовим выдачу', chipClass: 'mid', title: app.disbursement?.status === 'checking' ? 'Проверяем результат перечисления' : 'Готовим перечисление денег', what: app.disbursement?.status === 'checking' ? 'Банк сверяет статус операции. Повторно деньги не отправит' : 'Договор подписан', who: 'Банк', you: 'Ничего не нужно делать', banner: 'wait' };
    case 'ACTIVE':
      return { chip: 'Кредит выдан', chipClass: 'high', title: 'Кредит действует', what: 'Деньги на счёте', who: '—', you: 'Следите за датой следующего платежа', banner: 'success' };
    case 'REPAID':
      return { chip: 'Погашен', chipClass: 'high', title: 'Кредит полностью погашен', what: '—', who: '—', you: '—', banner: 'success' };
    case 'DECLINED':
      return { chip: 'Не одобрено', chipClass: 'low', title: 'Банк не может выдать кредит по текущим данным', what: 'Решение принято', who: '—', you: 'Посмотрите причины и советы', banner: 'decline' };
    case 'OFFER_REJECTED':
      return { chip: 'Вы отказались', chipClass: 'neutral', title: 'Вы отказались от предложения', what: '—', who: '—', you: 'Можно подать новую заявку', banner: 'decline' };
    case 'EXPIRED':
      return { chip: 'Предложение истекло', chipClass: 'neutral', title: 'Срок предложения истёк', what: '—', who: '—', you: 'Можно подать новую заявку', banner: 'decline' };
    case 'CANCELLED':
      return { chip: 'Отозвана', chipClass: 'neutral', title: 'Заявка отозвана', what: '—', who: '—', you: 'Можно подать новую заявку', banner: 'decline' };
  }
}

export const TASK_NAME: Record<TaskType, string> = {
  review: 'Решение по заявке',
  committee: 'Кредитный комитет',
  documents: 'Документы',
  compliance: 'Проверка по перечням',
  offer: 'Ждём ответ на оффер',
  signing: 'Подписание и выдача',
};

export const BANK_STATUS: Record<AppStatus, string> = {
  DRAFT: 'DRAFT · черновик',
  SUBMITTED: 'SUBMITTED',
  CHECKS: 'CHECKS · проверки',
  WAITING_SOURCE: 'WAITING_SOURCE',
  SCORING: 'SCORING',
  MANUAL_REVIEW: 'MANUAL_REVIEW',
  DOCS_REQUESTED: 'REQUEST_DOCS · ждём клиента',
  DOCS_REVIEW: 'DOCS_REVIEW',
  OFFER: 'OFFER · ждём клиента',
  SIGNING: 'SIGNING',
  DISBURSEMENT: 'DISBURSEMENT',
  ACTIVE: 'ACTIVE · выдан',
  REPAID: 'REPAID',
  DECLINED: 'DECLINED',
  OFFER_REJECTED: 'OFFER_REJECTED',
  EXPIRED: 'EXPIRED',
  CANCELLED: 'CANCELLED',
};

/** Куда вести клиента по заявке */
export function clientActionFor(app: ApplicationView): { label: string; to: string } | null {
  switch (app.status) {
    case 'DRAFT':
      return { label: 'Продолжить заявку', to: '/apply/goal' };
    case 'DOCS_REQUESTED':
      return { label: 'Открыть запрос', to: `/applications/${app.id}/documents` };
    case 'OFFER':
    case 'DECLINED':
    case 'EXPIRED':
    case 'OFFER_REJECTED':
      return { label: 'Посмотреть решение', to: `/applications/${app.id}/decision` };
    case 'SIGNING':
      return { label: 'Перейти к подписанию', to: `/applications/${app.id}/sign` };
    case 'DISBURSEMENT':
    case 'ACTIVE':
      return { label: 'Открыть кредит', to: `/applications/${app.id}/loan` };
    default:
      return null;
  }
}

/** Этап пути для ИИ-помощника: Шансы → Заявка → Проверка → Решение → Подпись → Выдача */
export function journeyIndex(status?: AppStatus): number {
  if (!status) return 0;
  if (status === 'DRAFT') return 1;
  if (['SUBMITTED', 'CHECKS', 'WAITING_SOURCE', 'SCORING', 'MANUAL_REVIEW', 'DOCS_REQUESTED', 'DOCS_REVIEW'].includes(status)) return 2;
  if (['OFFER', 'DECLINED', 'OFFER_REJECTED', 'EXPIRED'].includes(status)) return 3;
  if (status === 'SIGNING') return 4;
  return 5;
}
