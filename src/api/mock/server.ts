// Мок-сервер: имитирует бэкенд прямо в браузере.
// Состояние — в localStorage, поэтому заявку видно сразу в нескольких вкладках
// (клиент в одной, банк в другой). Фоновые шаги (проверки, скоринг, подпись, выдача)
// выполняет одна «ведущая» вкладка, чтобы не было двойной обработки.
import type { CreditApi, FileInput, LookupResult } from '../client';
import {
  ApiError,
  CHECK_SOURCES,
  isBankRole,
  type AiAnswer,
  type AiContext,
  type AppEvent,
  type Application,
  type ApplicationSummary,
  type ApplicationView,
  type BankTask,
  type ChancesResult,
  type CheckResult,
  type Company,
  type Decision,
  type DemoAccounts,
  type DocRequest,
  type DocRequestInput,
  type DraftInput,
  type ExtractedField,
  type Finance,
  type Loan,
  type Permissions,
  type Product,
  type Session,
  type SimLogEntry,
  type SourceId,
  type SourceMode,
  type SourceState,
  type User,
} from '../types';
import { AUTO_LIMIT, COMPANIES, PRODUCTS, PROFILES, RULES_VERSION, SOURCE_DELAY, USERS, initialSources, productByCode } from './db';
import { DSCR_MIN, REASONS, annuity, computeChances, computeScoring, fmt, makeOffer, maxAmountFor, monthlyPayment } from './scoring';
import { answerQuestion, draftDecisionText } from './ai';

const KEY = 'alfa-credit-mock-v3';
const LEADER_KEY = 'alfa-credit-mock-leader';

interface Job {
  id: string;
  appId: string;
  type: 'start_checks' | 'check' | 'scoring' | 'ocr' | 'ocr_statement' | 'esign' | 'disburse';
  runAt: number;
  source?: SourceId;
  docId?: string;
  attempt: number;
}

interface DbState {
  v: 3;
  seq: number;
  appSeq: number;
  apps: Application[];
  bkiConsents: Record<string, { at: string; by: string }>;
  chances: Record<string, ChancesResult>;
  sources: SourceState[];
  simLog: SimLogEntry[];
  jobs: Job[];
  idem: Record<string, string>;
}

const nowIso = () => new Date().toISOString();
const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString();
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const tabId = Math.random().toString(36).slice(2);

let memory: DbState | null = null;
let cacheRaw: string | null = null;
let storageOk = true;
try {
  localStorage.setItem('__t', '1');
  localStorage.removeItem('__t');
} catch {
  storageOk = false;
}

function load(): DbState {
  if (storageOk) {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        if (raw !== cacheRaw || !memory) {
          memory = JSON.parse(raw) as DbState;
          cacheRaw = raw;
        }
        return structuredClone(memory);
      }
    } catch {
      /* битые данные — пересоздаём */
    }
  }
  if (!memory) {
    memory = seed();
    save(memory);
  }
  return structuredClone(memory);
}

function save(s: DbState) {
  memory = s;
  if (storageOk) {
    try {
      cacheRaw = JSON.stringify(s);
      localStorage.setItem(KEY, cacheRaw);
    } catch {
      storageOk = false;
    }
  }
}

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === KEY) emit();
  });
}

function mutate<T>(fn: (s: DbState) => T): T {
  const s = load();
  const r = fn(s);
  save(s);
  emit();
  return r;
}

const id = (s: DbState, p: string) => `${p}-${(++s.seq).toString(36)}`;

// ───────── Справочники ─────────

const userById = (uid: string) => {
  const u = USERS.find((x) => x.id === uid);
  if (!u) throw new ApiError('unauthorized', 'Сессия не найдена. Войдите снова.');
  return u;
};
const companyById = (cid: string) => COMPANIES.find((c) => c.id === cid)!;
const src = (s: DbState, sid: SourceId) => s.sources.find((x) => x.id === sid)!;
const modeOf = (s: DbState, sid: SourceId): SourceMode => {
  const x = src(s, sid);
  return x.enabled ? x.mode : 'ERROR';
};
const roleName: Record<string, string> = {
  owner: 'владелец',
  accountant: 'бухгалтер',
  viewer: 'наблюдатель',
  manager: 'кредитный менеджер',
  underwriter: 'андеррайтер',
  compliance: 'комплаенс',
};

function addEvent(app: Application, e: Omit<AppEvent, 'id' | 'at'> & { at?: string }) {
  app.events.unshift({ id: `ev-${app.events.length + 1}-${Math.random().toString(36).slice(2, 6)}`, at: e.at ?? nowIso(), ...e });
}

function touch(app: Application) {
  app.version += 1;
  app.updatedAt = nowIso();
}

function setStatus(app: Application, st: Application['status']) {
  if (app.status !== st) {
    app.status = st;
    app.statusSince = nowIso();
  }
  touch(app);
}

function simLog(s: DbState, text: string, source?: SourceId, appId?: string) {
  s.simLog.unshift({ id: id(s, 'log'), at: nowIso(), text, source, appId });
  s.simLog = s.simLog.slice(0, 80);
}

function schedule(s: DbState, job: Omit<Job, 'id' | 'attempt'> & { attempt?: number }) {
  s.jobs.push({ id: id(s, 'job'), attempt: 0, ...job });
}

const emptyFinance = (companyId: string): Finance => {
  const p = PROFILES[companyId];
  const asOf = nowIso();
  return {
    revenueYear: { value: p.revenueYear, origin: 'registry', source: `ФНС, ${p.revenueAsOf}`, asOf },
    inflows3m: { value: p.inflowsAvg, origin: 'bank', source: 'Ваш счёт в банке, среднее за 3 мес', asOf },
    inflowTrendPct: { value: p.trendPct, origin: 'bank', source: 'Ваш счёт в банке', asOf },
    hasLoans: null,
    loanPayments: null,
    guarantor: 'none',
    guarantorName: '',
    comment: '',
  };
};

// ───────── Права ─────────

function permissions(app: Application, u: User, s: DbState): Permissions {
  const st = app.status;
  const isOwner = u.role === 'owner';
  const isClient = !isBankRole(u.role);
  const complianceOpen = !!app.checks.compliance?.match && !app.complianceResolved;
  const allChecksDone = CHECK_SOURCES.every((c) => ['ok', 'warning'].includes(app.checks[c]?.status ?? ''));
  const decidedThisRound = app.decisionHistory.some((d) => d.round === app.round && d.by !== 'system');
  return {
    editDraft: isClient && u.role !== 'viewer' && st === 'DRAFT',
    submit: isOwner && st === 'DRAFT',
    uploadDocs: isClient && u.role !== 'viewer' && (st === 'DOCS_REQUESTED' || st === 'DRAFT'),
    seeDocuments: u.role !== 'viewer',
    acceptOffer: isOwner && st === 'OFFER',
    sign: isOwner && st === 'SIGNING',
    cancel: isOwner && ['DRAFT', 'SUBMITTED', 'CHECKS', 'WAITING_SOURCE', 'SCORING', 'MANUAL_REVIEW', 'DOCS_REQUESTED', 'DOCS_REVIEW'].includes(st),
    takeTask: isBankRole(u.role) && !!taskFor(app, s) && taskFor(app, s)!.actionable && taskFor(app, s)!.role === u.role && app.assignee?.userId !== u.id,
    requestDocs: u.role === 'manager' && ['MANUAL_REVIEW', 'DOCS_REVIEW', 'CHECKS', 'WAITING_SOURCE'].includes(st),
    reviewDocs: u.role === 'manager' && st === 'DOCS_REVIEW',
    decide: u.role === 'underwriter' && st === 'MANUAL_REVIEW' && !complianceOpen && allChecksDone && !decidedThisRound,
    resolveCompliance: u.role === 'compliance' && complianceOpen,
    seeScoring: isBankRole(u.role),
  };
}

function taskFor(app: Application, _s?: DbState): { type: BankTask['type']; role: BankTask['role']; actionable: boolean } | null {
  const complianceOpen = !!app.checks.compliance?.match && !app.complianceResolved;
  switch (app.status) {
    case 'MANUAL_REVIEW':
      if (complianceOpen) return { type: 'compliance', role: 'compliance', actionable: true };
      return { type: app.committee ? 'committee' : 'review', role: 'underwriter', actionable: true };
    case 'DOCS_REVIEW':
      return { type: 'documents', role: 'manager', actionable: true };
    case 'DOCS_REQUESTED':
      return { type: 'documents', role: 'manager', actionable: false };
    case 'OFFER':
      return { type: 'offer', role: 'manager', actionable: false };
    case 'SIGNING':
    case 'DISBURSEMENT':
      return { type: 'signing', role: 'manager', actionable: false };
    default:
      return null;
  }
}

function view(app: Application, u: User, s: DbState): ApplicationView {
  const isClient = !isBankRole(u.role);
  if (isClient && u.companyId !== app.companyId) throw new ApiError('forbidden', 'Нет доступа к этой заявке');
  const v: ApplicationView = { ...structuredClone(app), viewerRole: u.role, permissions: permissions(app, u, s) };
  if (isClient) {
    v.events = v.events.filter((e) => e.client);
    if (v.scoring) v.afford = { cashFlow: v.scoring.cashFlow, currentPayments: v.scoring.currentPayments };
    delete v.scoring;
    v.scoringHistory = [];
    if (v.decision) v.decision = { ...v.decision, rulesVersion: '', internalComment: undefined };
    v.decisionHistory = v.decisionHistory.map((d) => ({ ...d, rulesVersion: '', internalComment: undefined }));
    delete v.assignee;
    if (u.role === 'viewer') {
      v.documents = v.documents.map((d) => ({ ...d, file: undefined, fields: [], answer: undefined }));
      if (v.finance.statement) v.finance.statement = undefined;
    }
  } else {
    const c = companyById(app.companyId);
    v.sensitive = u.role === 'compliance' || u.role === 'underwriter'
      ? { headPassport: '45 18 345678', headBirth: c.id === 'C' ? '12.06.1984' : '03.02.1979' }
      : { headPassport: '•••• ••5678', headBirth: '••.••.19••' };
  }
  return v;
}

function summary(app: Application): ApplicationSummary {
  const c = companyById(app.companyId);
  return {
    id: app.id,
    number: app.number,
    companyId: app.companyId,
    companyName: c.name,
    product: app.product,
    amount: app.amount,
    termMonths: app.termMonths,
    status: app.status,
    statusSince: app.statusSince,
    updatedAt: app.updatedAt,
    category: app.scoring?.category,
    score: app.scoring?.score,
    assignee: app.assignee?.name,
    offerAmount: app.offer?.amount,
  };
}

// ───────── Конвейер ─────────

function checkResult(app: Application, sid: SourceId): Pick<CheckResult, 'status' | 'summary' | 'match'> {
  const p = PROFILES[app.companyId];
  const c = companyById(app.companyId);
  switch (sid) {
    case 'egrul':
      return { status: 'ok', summary: `${c.type === 'IP' ? 'ИП' : 'Компания'} действует, руководитель совпадает с анкетой` };
    case 'fns_tax':
      if (p.taxDebt > 0) return { status: 'warning', summary: `Недоимка ${fmt(p.taxDebt)} ₽` };
      if (p.revenueYear === null) return { status: 'warning', summary: 'Отчётности ещё нет' };
      return { status: 'ok', summary: 'Недоимок нет, отчётность сдана' };
    case 'bki':
      if (p.overdueMaxDays > 0) return { status: 'warning', summary: p.overdueNote };
      return { status: 'ok', summary: p.overdueNote };
    case 'fssp':
      return { status: 'ok', summary: p.fsspSum ? `Производства на ${fmt(p.fsspSum)} ₽` : 'Производств нет' };
    case 'arbitr':
      return { status: p.arbitrDefendant ? 'warning' : 'ok', summary: p.arbitrNote };
    case 'compliance':
      return p.complianceMatch && !app.complianceResolved
        ? { status: 'warning', summary: 'Возможное совпадение по перечням: однофамилец руководителя', match: true }
        : { status: 'ok', summary: 'Совпадений нет' };
    default:
      return { status: 'ok' };
  }
}

const SOURCE_NAMES: Record<string, string> = Object.fromEntries(initialSources().map((x) => [x.id, x.name]));

function runCheck(s: DbState, app: Application, sid: SourceId, job: Job) {
  const mode = modeOf(s, sid);
  const chk = app.checks[sid] ?? { source: sid, status: 'pending', attempts: 0 };
  chk.attempts += 1;
  chk.requestedAt = chk.requestedAt ?? nowIso();
  const source = src(s, sid);
  if (mode === 'TIMEOUT' || mode === 'ERROR') {
    chk.status = 'waiting';
    app.checks[sid] = chk;
    source.lastCall = { at: nowIso(), result: mode === 'TIMEOUT' ? 'TIMEOUT' : 'ERROR', ms: SOURCE_DELAY[mode], appId: app.id };
    if (app.status !== 'WAITING_SOURCE') {
      app.waitingFor = sid;
      setStatus(app, 'WAITING_SOURCE');
      addEvent(app, {
        actor: 'source',
        actorName: SOURCE_NAMES[sid],
        client: `${SOURCE_NAMES[sid]} не ответил вовремя. Повторим запрос автоматически — это не отказ`,
        bank: `${SOURCE_NAMES[sid]} → ${mode}. Повтор запроса автоматически`,
      });
    }
    simLog(s, `Заявка ${app.number}: ${SOURCE_NAMES[sid]} → ${mode}, повтор через 5 с`, sid, app.id);
    schedule(s, { appId: app.id, type: 'check', source: sid, runAt: Date.now() + 5000, attempt: job.attempt + 1 });
    touch(app);
    return;
  }
  const r = checkResult(app, sid);
  Object.assign(chk, r, { answeredAt: nowIso() });
  app.checks[sid] = chk;
  source.lastCall = { at: nowIso(), result: 'SUCCESS', ms: SOURCE_DELAY[mode], appId: app.id };
  if (app.status === 'WAITING_SOURCE') {
    app.waitingFor = undefined;
    setStatus(app, 'CHECKS');
    addEvent(app, { actor: 'source', actorName: SOURCE_NAMES[sid], client: `${SOURCE_NAMES[sid]} ответил — продолжаем проверку`, bank: `${SOURCE_NAMES[sid]} → SUCCESS после повтора` });
    simLog(s, `Заявка ${app.number}: ${SOURCE_NAMES[sid]} восстановился, заявка продолжает проверку`, sid, app.id);
  } else {
    addEvent(app, { actor: 'source', actorName: SOURCE_NAMES[sid], bank: `${SOURCE_NAMES[sid]} → SUCCESS · ${r.summary ?? ''}` });
    simLog(s, `Заявка ${app.number}: ${SOURCE_NAMES[sid]} → SUCCESS`, sid, app.id);
  }
  touch(app);
  const idx = CHECK_SOURCES.indexOf(sid);
  const next = CHECK_SOURCES[idx + 1];
  if (next) {
    app.checks[next] = { source: next, status: 'running', attempts: 0, requestedAt: nowIso() };
    schedule(s, { appId: app.id, type: 'check', source: next, runAt: Date.now() + SOURCE_DELAY[modeOf(s, next)] });
  } else {
    addEvent(app, { actor: 'system', actorName: 'Система', client: 'Данные проверены: ФНС, бюро кредитных историй, суды, приставы', bank: 'Все проверки завершены' });
    setStatus(app, 'SCORING');
    schedule(s, { appId: app.id, type: 'scoring', runAt: Date.now() + 1400 });
  }
}

function adviceFor(codes: string[], app: Application): string[] {
  const p = PROFILES[app.companyId];
  const out: string[] = [];
  if (codes.includes('HS3')) out.push(`Погасите долг перед налоговой ${fmt(p.taxDebt)} ₽ — после обновления данных ФНС можно подать заявку снова`);
  if (codes.includes('HS4')) out.push('Платите текущие кредиты без просрочек: через 12 месяцев после просрочки 90+ этот стоп-фактор перестанет действовать');
  if (codes.includes('AFFORD')) out.push('Можно взять меньшую сумму или увеличить срок — платёж станет ниже');
  if (codes.includes('TREND')) out.push('Если часть оборотов в другом банке — приложите выписку');
  if (codes.includes('OVERDUE')) out.push('Без новых просрочек оценка со временем улучшится');
  if (!out.length) out.push('Посмотрите на главной, какой продукт предварительно подходит');
  return out;
}

function clientTextFor(outcome: Decision['outcome'], codes: string[], amount?: number): string {
  const reasons = codes.map((c) => REASONS[c]?.plain).filter(Boolean);
  switch (outcome) {
    case 'APPROVE':
      return 'Банк одобрил заявку на запрошенных условиях. Проверьте условия и подпишите договор в кабинете.';
    case 'COUNTER_OFFER':
      return `Банк готов выдать ${amount ? fmt(amount) + ' ₽' : 'кредит'} на других условиях. ${reasons.length ? 'Причина: ' + reasons.join('; ').toLowerCase() + '.' : ''}`.trim();
    case 'DECLINE':
      return `По текущим данным банк не может выдать кредит. ${reasons.length ? 'Причины: ' + reasons.join('; ').toLowerCase() + '.' : ''} Это решение по текущим данным — когда причины уйдут, можно подать заявку снова.`;
    case 'REQUEST_DOCS':
      return 'Чтобы принять решение, банку нужен документ. Это не отказ — после проверки заявка продолжит рассмотрение.';
    default:
      return 'Заявку дополнительно проверит сотрудник банка. Это не отказ.';
  }
}

function createDocRequest(s: DbState, app: Application, input: DocRequestInput, by: string): DocRequest {
  const isStatement = input.type === 'bank_statement';
  const d: DocRequest = {
    id: id(s, 'doc'),
    type: input.type,
    title: input.title,
    why: input.why,
    requirements: isStatement
      ? 'Выписка по всем счетам в других банках за последние 6 месяцев, с оборотами по месяцам'
      : input.type === 'tax_return'
        ? 'Последняя налоговая декларация с отметкой о приёме'
        : input.type === 'info'
          ? 'Ответьте текстом в кабинете'
          : 'Скан или файл документа целиком, все страницы',
    formats: input.type === 'info' ? [] : ['PDF', 'XLSX', 'CSV', 'JPG', 'PNG'],
    maxSizeMb: 10,
    deadline: input.deadline,
    requestedBy: by,
    requestedAt: nowIso(),
    comment: input.comment || undefined,
    status: 'required',
    fields: [],
  };
  app.documents.push(d);
  return d;
}

function runScoring(s: DbState, app: Application) {
  const c = companyById(app.companyId);
  const statementAccepted = app.documents.some((d) => d.type === 'bank_statement' && d.status === 'accepted') || app.finance.statement?.status === 'confirmed';
  const complianceOpen = !!app.checks.compliance?.match && !app.complianceResolved;
  const sc = computeScoring(
    {
      app,
      company: c,
      profile: PROFILES[app.companyId],
      statementAccepted,
      bkiOk: app.checks.bki?.status === 'ok' || app.checks.bki?.status === 'warning',
      complianceOpen,
      complianceConfirmed: app.complianceResolved?.verdict === 'confirmed',
    },
    id(s, 'sc'),
  );
  app.scoring = sc;
  app.needsRescore = false;
  app.scoringHistory.unshift({ id: sc.id, round: app.round, at: sc.at, score: sc.score, category: sc.category, trigger: app.round > 1 ? 'Новые документы' : 'Первичная оценка' });
  addEvent(app, { actor: 'system', actorName: 'Скоринг', bank: `Скоринг ${sc.rulesVersion}: ${sc.score}/100, категория ${sc.category}, DSCR ${sc.dscr.toFixed(2).replace('.', ',')} → рекомендация ${sc.recommendation.outcome}` });
  const rec = sc.recommendation;
  const req = { product: app.product, amount: app.amount, termMonths: app.termMonths };
  const guarantor = app.finance.guarantor === 'none' ? 'Не требуется' : app.finance.guarantor === 'owner' ? 'Владелец бизнеса' : app.finance.guarantorName || 'Третье лицо';

  const decide = (outcome: Decision['outcome'], extra?: Partial<Decision>) => {
    const dec: Decision = {
      id: id(s, 'dec'),
      round: app.round,
      outcome,
      by: 'system',
      byName: 'Система',
      at: nowIso(),
      reasons: rec.reasonCodes.map((r) => REASONS[r]).filter(Boolean),
      clientText: clientTextFor(outcome, rec.reasonCodes, rec.amount),
      rulesVersion: RULES_VERSION,
      advice: adviceFor(rec.reasonCodes, app),
      ...extra,
    };
    app.decision = dec;
    app.decisionHistory.unshift(dec);
    return dec;
  };

  switch (rec.outcome) {
    case 'APPROVE': {
      decide('APPROVE');
      app.offer = makeOffer({ id: id(s, 'of'), version: (app.offer?.version ?? 0) + 1, kind: 'full', product: app.product, amount: app.amount, termMonths: app.termMonths, requested: req, guarantor });
      setStatus(app, 'OFFER');
      addEvent(app, { actor: 'system', actorName: 'Система', client: 'Банк одобрил заявку на ваших условиях', bank: 'Автоматическое одобрение (категория A/B, DSCR в норме)' });
      break;
    }
    case 'COUNTER_OFFER': {
      decide('COUNTER_OFFER');
      app.offer = makeOffer({ id: id(s, 'of'), version: (app.offer?.version ?? 0) + 1, kind: 'counter', product: app.product, amount: rec.amount!, termMonths: rec.termMonths ?? app.termMonths, requested: req, guarantor });
      setStatus(app, 'OFFER');
      addEvent(app, { actor: 'system', actorName: 'Система', client: `Банк предложил другие условия: ${fmt(rec.amount!)} ₽`, bank: `Автоматическое встречное предложение ${fmt(rec.amount!)} ₽` });
      break;
    }
    case 'REQUEST_DOCS': {
      const dec = decide('REQUEST_DOCS');
      const isData = rec.reasonCodes.includes('DATA');
      createDocRequest(
        s,
        app,
        {
          type: 'bank_statement',
          title: isData ? 'Выписка по счетам за все месяцы работы' : 'Выписка из другого банка',
          why: isData
            ? 'Отчётности в ФНС ещё нет. По выписке банк увидит обороты и сможет посчитать условия.'
            : 'Поступления на счёт в нашем банке упали. Если часть оборотов идёт через другой банк, выписка покажет полную картину. Документ нужен для уточнения финансовых показателей.',
          deadline: new Date(Date.now() + 3 * 86400_000).toISOString(),
          comment: '',
        },
        'Система',
      );
      setStatus(app, 'DOCS_REQUESTED');
      addEvent(app, { actor: 'system', actorName: 'Система', client: 'Банк попросил документ. Это не отказ — после проверки рассмотрение продолжится', bank: `Запрос документов: ${dec.reasons.map((r) => r.code).join(', ')}` });
      break;
    }
    case 'DECLINE': {
      decide('DECLINE');
      setStatus(app, 'DECLINED');
      addEvent(app, { actor: 'system', actorName: 'Система', client: 'Банк не может выдать кредит по текущим данным. Причины и советы — в решении', bank: `Автоматический отказ: ${rec.reasonCodes.join(', ')}` });
      break;
    }
    default: {
      setStatus(app, 'MANUAL_REVIEW');
      if (complianceOpen) {
        addEvent(app, { actor: 'system', actorName: 'Система', client: 'Заявку дополнительно проверяет банк. Это не отказ', bank: 'Нужна проверка комплаенса: возможное совпадение по перечням' });
      } else {
        addEvent(app, { actor: 'system', actorName: 'Система', client: 'Заявку дополнительно проверяет сотрудник банка. Это не отказ', bank: `Передано андеррайтеру: ${rec.reasonCodes.join(', ') || 'категория ' + sc.category}` });
      }
    }
  }
}

function extractFields(app: Application, kind: 'statement' | 'doc'): ExtractedField[] {
  const p = PROFILES[app.companyId];
  const other = p.statement?.otherBankInflows ?? Math.round(p.inflowsAvg * 0.3);
  const months = app.companyId === 'D' ? 5 : 6;
  return [
    { key: 'bank', label: 'Банк', value: 'ПАО «Пример-Банк»', confirmed: false },
    { key: 'period', label: 'Период', value: `${months} мес: 05.2026 — 10.2026`, confirmed: false },
    { key: 'avg', label: 'Среднемесячные поступления', value: `${fmt(kind === 'statement' ? other : app.companyId === 'D' ? 480_000 : other)} ₽`, confirmed: false },
    { key: 'total', label: 'Поступления за период', value: `${fmt((app.companyId === 'D' ? 480_000 : other) * months)} ₽`, confirmed: false },
  ];
}

function processJob(s: DbState, job: Job) {
  const app = s.apps.find((a) => a.id === job.appId);
  if (!app) return;
  switch (job.type) {
    case 'start_checks': {
      setStatus(app, 'CHECKS');
      addEvent(app, { actor: 'system', actorName: 'Система', client: 'Начали проверку данных', bank: 'Запущены проверки внешних источников' });
      const first = CHECK_SOURCES[0];
      app.checks[first] = { source: first, status: 'running', attempts: 0, requestedAt: nowIso() };
      schedule(s, { appId: app.id, type: 'check', source: first, runAt: Date.now() + SOURCE_DELAY[modeOf(s, first)] });
      break;
    }
    case 'check':
      runCheck(s, app, job.source!, job);
      break;
    case 'scoring':
      runScoring(s, app);
      break;
    case 'ocr':
    case 'ocr_statement': {
      const mode = modeOf(s, 'ocr');
      const ok = mode === 'SUCCESS' || mode === 'SLOW';
      src(s, 'ocr').lastCall = { at: nowIso(), result: ok ? 'SUCCESS' : mode === 'TIMEOUT' ? 'TIMEOUT' : 'ERROR', ms: SOURCE_DELAY[mode], appId: app.id };
      simLog(s, `Заявка ${app.number}: распознавание → ${ok ? 'SUCCESS' : mode}`, 'ocr', app.id);
      if (job.type === 'ocr_statement' && app.finance.statement) {
        app.finance.statement.status = 'check';
        if (ok) app.finance.statement.fields = extractFields(app, 'statement');
        else {
          app.finance.statement.fields = extractFields(app, 'statement').map((f) => ({ ...f, value: '' }));
          app.finance.statement.error = 'Не удалось распознать файл. Заполните поля вручную или замените файл.';
        }
      } else {
        const d = app.documents.find((x) => x.id === job.docId);
        if (d) {
          d.status = 'check';
          if (ok) {
            d.fields = extractFields(app, 'doc');
            d.extractError = undefined;
          } else {
            d.fields = extractFields(app, 'doc').map((f) => ({ ...f, value: '' }));
            d.extractError = 'Не удалось распознать файл. Заполните поля вручную или замените файл.';
          }
        }
      }
      touch(app);
      break;
    }
    case 'esign': {
      const mode = modeOf(s, 'esign');
      const ok = mode === 'SUCCESS' || mode === 'SLOW';
      src(s, 'esign').lastCall = { at: nowIso(), result: ok ? 'SUCCESS' : mode === 'TIMEOUT' ? 'TIMEOUT' : 'ERROR', ms: SOURCE_DELAY[mode], appId: app.id };
      if (!app.signing) break;
      if (!ok) {
        app.signing.status = 'error';
        app.signing.error = 'Сервис подписи не ответил. Договор не подписан — попробуйте ещё раз.';
        addEvent(app, { actor: 'source', actorName: 'Электронная подпись', client: 'Подпись не прошла: сервис подписи недоступен. Договор не подписан', bank: `ЭП → ${mode}` });
        simLog(s, `Заявка ${app.number}: подпись → ${mode}`, 'esign', app.id);
        touch(app);
        break;
      }
      app.signing.status = 'signed';
      app.signing.signedAt = nowIso();
      app.signing.participants = app.signing.participants.map((p) => (p.status === 'waiting' ? { ...p, status: 'signed', at: nowIso() } : p));
      app.disbursement = { status: 'preparing', attempts: 0, operationId: id(s, 'op') };
      setStatus(app, 'DISBURSEMENT');
      addEvent(app, { actor: 'client', actorName: userNameFor(app.companyId, 'owner'), client: 'Договор подписан. Готовим перечисление денег', bank: 'Договор подписан ЭП владельца' });
      simLog(s, `Заявка ${app.number}: договор подписан`, 'esign', app.id);
      schedule(s, { appId: app.id, type: 'disburse', runAt: Date.now() + 3000 });
      break;
    }
    case 'disburse': {
      const mode = modeOf(s, 'abs');
      const ok = mode === 'SUCCESS' || mode === 'SLOW';
      src(s, 'abs').lastCall = { at: nowIso(), result: ok ? 'SUCCESS' : mode === 'TIMEOUT' ? 'TIMEOUT' : 'ERROR', ms: SOURCE_DELAY[mode], appId: app.id };
      if (!app.disbursement || app.disbursement.status === 'done') break;
      app.disbursement.attempts += 1;
      if (!ok) {
        if (app.disbursement.status !== 'checking') {
          addEvent(app, { actor: 'source', actorName: 'Выдача', client: 'Проверяем результат перечисления. Повторно деньги не отправим — дождитесь подтверждения', bank: `АБС → ${mode}, операция ${app.disbursement.operationId}: сверяем статус` });
        }
        app.disbursement.status = 'checking';
        simLog(s, `Заявка ${app.number}: выдача → ${mode}, сверяем операцию ${app.disbursement.operationId}`, 'abs', app.id);
        schedule(s, { appId: app.id, type: 'disburse', runAt: Date.now() + 5000, attempt: job.attempt + 1 });
        touch(app);
        break;
      }
      app.disbursement.status = 'done';
      app.disbursement.doneAt = nowIso();
      app.loan = buildLoan(app);
      setStatus(app, 'ACTIVE');
      addEvent(app, { actor: 'system', actorName: 'Выдача', client: `${fmt(app.offer!.amount)} ₽ ${app.offer!.product === 'overdraft' ? '— лимит открыт' : 'зачислены на ваш счёт'}`, bank: `Выдача подтверждена, операция ${app.disbursement.operationId}` });
      simLog(s, `Заявка ${app.number}: выдача подтверждена`, 'abs', app.id);
      break;
    }
  }
}

function userNameFor(companyId: string, role: string) {
  return USERS.find((u) => u.companyId === companyId && u.role === role)?.name ?? 'Клиент';
}

function buildLoan(app: Application, paidCount = 0): Loan {
  const o = app.offer!;
  const p = productByCode(o.product);
  const schedule: Loan['schedule'] = [];
  let balance = o.amount;
  const start = new Date();
  if (p.kind === 'loan') {
    const pay = annuity(o.amount, o.ratePct, o.termMonths);
    for (let n = 1; n <= o.termMonths; n++) {
      const interest = (balance * o.ratePct) / 100 / 12;
      const principal = pay - interest;
      balance -= principal;
      const d = new Date(start.getFullYear(), start.getMonth() + n, Math.min(start.getDate(), 28));
      schedule.push({ n, date: d.toISOString(), amount: Math.round(pay), principal: Math.round(principal), interest: Math.round(interest), status: n <= paidCount ? 'paid' : 'scheduled' });
    }
  }
  const paidPrincipal = schedule.filter((x) => x.status === 'paid').reduce((a, x) => a + x.principal, 0);
  return {
    product: o.product,
    amount: o.amount,
    used: p.kind === 'limit' ? 0 : o.amount,
    balance: p.kind === 'limit' ? 0 : o.amount - paidPrincipal,
    ratePct: o.ratePct,
    termMonths: o.termMonths,
    schedule,
    account: '40702 810 •••• •••• 1234',
  };
}

// ───────── Ведущая вкладка выполняет фоновые задачи ─────────

function isLeader(): boolean {
  if (!storageOk) return true;
  try {
    const raw = localStorage.getItem(LEADER_KEY);
    const now = Date.now();
    const cur = raw ? (JSON.parse(raw) as { tab: string; until: number }) : null;
    if (!cur || cur.until < now || cur.tab === tabId) {
      localStorage.setItem(LEADER_KEY, JSON.stringify({ tab: tabId, until: now + 3000 }));
      return true;
    }
    return false;
  } catch {
    return true;
  }
}

function tick() {
  if (!isLeader()) return;
  const s = load();
  const now = Date.now();
  const due = s.jobs.filter((j) => j.runAt <= now).sort((a, b) => a.runAt - b.runAt);
  if (!due.length) {
    expireOffers();
    return;
  }
  mutate((st) => {
    for (const j of due) {
      st.jobs = st.jobs.filter((x) => x.id !== j.id);
      processJob(st, j);
    }
  });
}

function expireOffers() {
  const s = load();
  const now = Date.now();
  if (!s.apps.some((a) => a.status === 'OFFER' && a.offer && new Date(a.offer.validUntil).getTime() < now)) return;
  mutate((st) => {
    st.apps.forEach((a) => {
      if (a.status === 'OFFER' && a.offer && new Date(a.offer.validUntil).getTime() < now) {
        setStatus(a, 'EXPIRED');
        addEvent(a, { actor: 'system', actorName: 'Система', client: 'Срок действия предложения истёк. Можно подать новую заявку', bank: 'Оффер истёк' });
      }
    });
  });
}

if (typeof window !== 'undefined') setInterval(tick, 400);

// ───────── Seed ─────────

function baseApp(_s: DbState, companyId: string, number: string, input: DraftInput, createdMinAgo: number): Application {
  const owner = USERS.find((u) => u.companyId === companyId && u.role === 'owner')!;
  return {
    id: `app-${number}`,
    number,
    companyId,
    createdBy: owner.id,
    createdAt: ago(createdMinAgo),
    updatedAt: ago(createdMinAgo),
    version: 1,
    round: 1,
    ...input,
    companyConfirmed: 'registry',
    delegatedToAccountant: false,
    finance: { ...emptyFinance(companyId), hasLoans: PROFILES[companyId].currentPayments > 0, loanPayments: PROFILES[companyId].currentPayments || null },
    consents: { bki: { at: ago(createdMinAgo), by: owner.name }, pd: { at: ago(createdMinAgo), by: owner.name } },
    status: 'DRAFT',
    statusSince: ago(createdMinAgo),
    submittedBy: { userId: owner.id, name: owner.name, role: 'owner', at: ago(createdMinAgo) },
    checks: {},
    scoringHistory: [],
    documents: [],
    decisionHistory: [],
    events: [],
  };
}

function instantPipeline(s: DbState, app: Application, minAgo: number) {
  for (const c of CHECK_SOURCES) {
    app.checks[c] = { source: c, attempts: 1, requestedAt: ago(minAgo), answeredAt: ago(minAgo - 1), ...checkResult(app, c) };
  }
  addEvent(app, { actor: 'client', actorName: app.submittedBy!.name, client: 'Вы отправили заявку', bank: 'Заявка отправлена клиентом', at: ago(minAgo) });
  runScoring(s, app);
  const t = ago(minAgo - 2);
  app.events.forEach((e) => (e.at = e.at > ago(minAgo) ? t : e.at));
  if (app.scoring) app.scoring.at = t;
  if (app.decision) app.decision.at = t;
  app.decisionHistory.forEach((d) => (d.at = t));
  app.scoringHistory.forEach((h) => (h.at = t));
  app.statusSince = t;
  app.updatedAt = t;
}

function seed(): DbState {
  const s: DbState = { v: 3, seq: 100, appSeq: 42, apps: [], bkiConsents: {}, chances: {}, sources: initialSources(), simLog: [], jobs: [], idem: {} };
  // A — действующий кредит
  const a = baseApp(s, 'A', '2026-10-0041', { product: 'working_capital', goal: 'purchase', amount: 3_000_000, termMonths: 12, when: 'week' }, 60 * 24 * 40);
  instantPipeline(s, a, 60 * 24 * 40);
  a.offer!.acceptedAt = ago(60 * 24 * 39);
  a.signing = { status: 'signed', signedAt: ago(60 * 24 * 39), participants: [{ name: 'Иванов А. С.', role: 'Владелец, подписант', status: 'signed', at: ago(60 * 24 * 39) }] };
  a.disbursement = { status: 'done', attempts: 1, operationId: 'op-seed-41', doneAt: ago(60 * 24 * 39) };
  a.loan = buildLoan(a, 1);
  a.status = 'ACTIVE';
  a.statusSince = ago(60 * 24 * 39);
  addEvent(a, { actor: 'system', actorName: 'Выдача', client: '3 000 000 ₽ зачислены на ваш счёт', bank: 'Выдача подтверждена', at: ago(60 * 24 * 39) });
  addEvent(a, { actor: 'system', actorName: 'Сопровождение', client: 'Платёж №1 оплачен', bank: 'Платёж №1 оплачен', at: ago(60 * 24 * 9) });
  s.apps.push(a);
  // E — отказ
  const e = baseApp(s, 'E', '2026-10-0040', { product: 'working_capital', goal: 'purchase', amount: 2_000_000, termMonths: 12, when: 'week' }, 60 * 26);
  instantPipeline(s, e, 60 * 26);
  e.statusSince = ago(60 * 26 - 3);
  s.apps.push(e);
  // B — ручная проверка + комплаенс
  const b = baseApp(s, 'B', '2026-10-0039', { product: 'development', goal: 'equipment', amount: 8_000_000, termMonths: 36, when: 'month' }, 95);
  b.finance.guarantor = 'owner';
  instantPipeline(s, b, 95);
  b.statusSince = ago(80);
  s.apps.push(b);
  s.bkiConsents.A = { at: ago(60 * 24 * 40), by: 'Иванов А. С.' };
  s.bkiConsents.B = { at: ago(100), by: 'Соколова М. И.' };
  s.bkiConsents.E = { at: ago(60 * 26), by: 'Волков Е. П.' };
  s.simLog.push({ id: 'log-seed', at: nowIso(), text: 'Демо-данные созданы. Все источники работают' });
  return s;
}

// ───────── API ─────────

const net = (min = 120, max = 280) => sleep(min + Math.random() * (max - min));

function getApp(s: DbState, appId: string) {
  const a = s.apps.find((x) => x.id === appId);
  if (!a) throw new ApiError('not_found', 'Заявка не найдена');
  return a;
}

function requireRole(u: User, roles: string[], what: string) {
  if (!roles.includes(u.role)) throw new ApiError('forbidden', `${what} может только: ${roles.map((r) => roleName[r]).join(', ')}`);
}

function requireCompany(u: User, app: Application) {
  if (!isBankRole(u.role) && u.companyId !== app.companyId) throw new ApiError('forbidden', 'Нет доступа к заявке');
}

function idem<T>(s: DbState, key: string, appId: string, fn: () => T): T | null {
  if (s.idem[key]) return null; // повтор — действие уже выполнено
  s.idem[key] = appId;
  return fn();
}

async function sourceGate(sid: SourceId) {
  const s = load();
  const mode = modeOf(s, sid);
  if (mode === 'SLOW') await sleep(SOURCE_DELAY.SLOW);
  if (mode === 'TIMEOUT') {
    await sleep(SOURCE_DELAY.TIMEOUT);
    return 'TIMEOUT' as const;
  }
  if (mode === 'ERROR') return 'ERROR' as const;
  return 'OK' as const;
}

function validateFile(f: FileInput) {
  const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
  if (!['pdf', 'xlsx', 'xls', 'csv', 'jpg', 'jpeg', 'png'].includes(ext)) throw new ApiError('file_type', 'Неподходящий формат. Подойдут PDF, XLSX, CSV, JPG или PNG');
  if (f.size > 10 * 1024 * 1024) throw new ApiError('file_size', 'Файл больше 10 МБ. Сожмите его или разделите на части');
  if (f.size === 0) throw new ApiError('file_empty', 'Файл пустой');
}

function newApp(s: DbState, u: User, input: DraftInput): Application {
  const number = `2026-10-${String(s.appSeq++).padStart(4, '0')}`;
  const consent = s.bkiConsents[u.companyId!];
  return {
    id: `app-${number}`,
    number,
    companyId: u.companyId!,
    createdBy: u.id,
    createdAt: nowIso(),
    updatedAt: nowIso(),
    version: 1,
    round: 1,
    ...input,
    companyConfirmed: null,
    delegatedToAccountant: false,
    finance: emptyFinance(u.companyId!),
    consents: consent ? { bki: consent } : {},
    status: 'DRAFT',
    statusSince: nowIso(),
    checks: {},
    scoringHistory: [],
    documents: [],
    decisionHistory: [],
    events: [],
  };
}

function submitInternal(s: DbState, app: Application, u: User) {
  app.submittedBy = { userId: u.id, name: u.name, role: u.role, at: nowIso() };
  CHECK_SOURCES.forEach((c) => (app.checks[c] = { source: c, status: 'pending', attempts: 0 }));
  setStatus(app, 'SUBMITTED');
  addEvent(app, { actor: 'client', actorName: u.name, client: `Вы отправили заявку (${roleName[u.role]})`, bank: `Заявка отправлена: ${u.name}, ${roleName[u.role]}` });
  schedule(s, { appId: app.id, type: 'start_checks', runAt: Date.now() + 900 });
}

export function createMockApi(): CreditApi {
  return {
    mode: 'mock',

    async getDemoAccounts(): Promise<DemoAccounts> {
      await net(60, 120);
      return { companies: COMPANIES, users: USERS };
    },
    async getUser(sess: Session) {
      await net(30, 60);
      return userById(sess.userId);
    },
    async getProducts(): Promise<Product[]> {
      return PRODUCTS;
    },
    async getCompany(sess, companyId): Promise<Company> {
      await net(60, 120);
      const u = userById(sess.userId);
      if (!isBankRole(u.role) && u.companyId !== companyId) throw new ApiError('forbidden', 'Нет доступа');
      return companyById(companyId);
    },

    async getChances(sess, companyId, opts) {
      const u = userById(sess.userId);
      if (!isBankRole(u.role) && u.companyId !== companyId) throw new ApiError('forbidden', 'Нет доступа');
      let s = load();
      const cached = s.chances[companyId];
      const consent = !!s.bkiConsents[companyId];
      if (cached && !opts?.refresh && cached.bkiConsent === consent) {
        await net(80, 160);
        return cached;
      }
      await net(300, 600);
      // обновление идёт через ФНС (и БКИ при согласии)
      const fns = await sourceGate('fns_tax');
      const bki = consent ? await sourceGate('bki') : 'OK';
      s = load();
      if (fns !== 'OK' || bki !== 'OK') {
        const which = fns !== 'OK' ? 'ФНС' : 'БКИ';
        const base = cached ?? computeChances(companyById(companyId), PROFILES[companyId], consent, ago(60 * 3));
        return { ...base, state: 'error', error: `Не удалось обновить данные ${which}. Показываем оценку от ${new Date(base.calculatedAt).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}` };
      }
      const res = computeChances(companyById(companyId), PROFILES[companyId], consent, nowIso());
      mutate((st) => {
        st.chances[companyId] = res;
      });
      return res;
    },

    async giveBkiConsent(sess, companyId) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['owner'], 'Дать согласие');
      mutate((s) => {
        s.bkiConsents[companyId] = { at: nowIso(), by: u.name };
        delete s.chances[companyId];
        s.apps.filter((a) => a.companyId === companyId && a.status === 'DRAFT').forEach((a) => (a.consents.bki = s.bkiConsents[companyId]));
      });
    },

    async listApplications(sess) {
      await net(80, 160);
      const u = userById(sess.userId);
      const s = load();
      return s.apps.filter((a) => a.companyId === u.companyId).map(summary).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },

    async getApplication(sess, appId) {
      await net(60, 140);
      const u = userById(sess.userId);
      const s = load();
      return view(getApp(s, appId), u, s);
    },

    async createDraft(sess, input) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['owner', 'accountant'], 'Создать заявку');
      return mutate((s) => {
        const existing = s.apps.find((a) => a.companyId === u.companyId && a.status === 'DRAFT');
        const app = existing ?? newApp(s, u, input);
        if (existing) Object.assign(existing, input);
        else s.apps.push(app);
        touch(app);
        return view(app, u, s);
      });
    },

    async updateDraft(sess, appId, patch) {
      await net(80, 150);
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (!permissions(app, u, s).editDraft) throw new ApiError('forbidden', 'Черновик может менять владелец или бухгалтер');
        const { finance, ...rest } = patch;
        Object.assign(app, rest);
        if (finance) app.finance = { ...app.finance, ...finance };
        if (patch.delegatedToAccountant) addEvent(app, { actor: 'client', actorName: u.name, client: 'Финансы переданы бухгалтеру. Ожидаем заполнения', bank: 'Делегировано бухгалтеру' });
        touch(app);
        return view(app, u, s);
      });
    },

    async lookupCompany(sess, appId, inn): Promise<LookupResult> {
      const u = userById(sess.userId);
      const clean = inn.replace(/\D/g, '');
      if (!(clean.length === 10 || clean.length === 12)) {
        await net(40, 80);
        return { status: 'invalid', message: 'ИНН — это 10 цифр для ООО или 12 цифр для ИП' };
      }
      await net(400, 700);
      const gate = await sourceGate('egrul');
      mutate((s) => {
        const x = src(s, 'egrul');
        x.lastCall = { at: nowIso(), result: gate === 'OK' ? 'SUCCESS' : gate, ms: SOURCE_DELAY[x.mode], appId };
        simLog(s, `Поиск по ИНН ${clean}: ЕГРЮЛ → ${gate === 'OK' ? 'SUCCESS' : gate}`, 'egrul', appId);
      });
      if (gate !== 'OK') return { status: 'unavailable', message: 'Реестр ФНС сейчас не отвечает. Черновик сохранён — попробуйте ещё раз или уточните данные вручную' };
      const c = COMPANIES.find((x) => x.inn === clean);
      if (!c) return { status: 'not_found', message: 'Компания с таким ИНН не найдена в реестре. Проверьте цифры' };
      if (c.id !== u.companyId) return { status: 'not_found', message: 'Этот ИНН не относится к вашей компании в кабинете. Проверьте цифры' };
      return { status: 'found', company: c, asOf: nowIso() };
    },

    async confirmCompany(sess, appId, how, note) {
      await net();
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        app.companyConfirmed = how;
        app.manualCompanyNote = note;
        if (how === 'manual') addEvent(app, { actor: 'client', actorName: u.name, client: 'Вы уточнили данные компании вручную — банк проверит их при рассмотрении', bank: `Ручное уточнение компании: ${note ?? ''}` });
        touch(app);
        return view(app, u, s);
      });
    },

    async uploadStatement(sess, appId, file) {
      await net(300, 500);
      const u = userById(sess.userId);
      validateFile(file);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        app.finance.statement = { file: { ...file, uploadedAt: nowIso() }, status: 'extracting', fields: [] };
        schedule(s, { appId, type: 'ocr_statement', runAt: Date.now() + SOURCE_DELAY[modeOf(s, 'ocr')] + 600 });
        touch(app);
        return view(app, u, s);
      });
    },

    async confirmStatementFields(sess, appId, fields) {
      await net();
      const u = userById(sess.userId);
      if (fields.some((f) => !f.value.trim())) throw new ApiError('validation', 'Заполните все поля выписки');
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (!app.finance.statement) throw new ApiError('validation', 'Файл не загружен');
        app.finance.statement.fields = fields.map((f) => ({ ...f, confirmed: true }));
        app.finance.statement.status = 'confirmed';
        app.finance.statement.error = undefined;
        touch(app);
        return view(app, u, s);
      });
    },

    async removeStatement(sess, appId) {
      await net(80, 120);
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        app.finance.statement = undefined;
        touch(app);
        return view(app, u, s);
      });
    },

    async giveConsents(sess, appId) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['owner'], 'Дать согласия');
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        const c = { at: nowIso(), by: u.name };
        app.consents = { bki: app.consents.bki ?? c, pd: c };
        s.bkiConsents[app.companyId] = s.bkiConsents[app.companyId] ?? c;
        touch(app);
        return view(app, u, s);
      });
    },

    async submitApplication(sess, appId, key) {
      const u = userById(sess.userId);
      let s = load();
      const app0 = getApp(s, appId);
      requireCompany(u, app0);
      if (s.idem[key]) return view(app0, u, s);
      requireRole(u, ['owner'], 'Отправить заявку');
      if (app0.status !== 'DRAFT') return view(app0, u, s);
      const p = productByCode(app0.product);
      const missing: string[] = [];
      if (!app0.companyConfirmed) missing.push('компания не подтверждена');
      if (app0.finance.hasLoans === null) missing.push('не указано, есть ли кредиты');
      if (app0.finance.hasLoans && !app0.finance.loanPayments) missing.push('не указан платёж по кредитам');
      if (app0.finance.revenueYear.value === null && app0.finance.statement?.status !== 'confirmed') missing.push('нет выручки: приложите выписку');
      if (!app0.consents.bki || !app0.consents.pd) missing.push('нет согласий');
      if (app0.amount < p.amountMin || app0.amount > p.amountMax) missing.push('сумма вне диапазона продукта');
      if (missing.length) throw new ApiError('validation', `Нельзя отправить: ${missing.join(', ')}`);
      await net(400, 700);
      const gate = await sourceGate('gateway');
      if (gate !== 'OK') {
        mutate((st) => simLog(st, `Отправка заявки ${app0.number}: приём заявок → ${gate}`, 'gateway', appId));
        throw new ApiError('gateway', 'Не удалось отправить заявку: сервис приёма не ответил. Данные сохранены — попробуйте ещё раз', true);
      }
      return mutate((st) => {
        s = st;
        const app = getApp(st, appId);
        idem(st, key, appId, () => {
          if (app.status === 'DRAFT') submitInternal(st, app, u);
        });
        return view(app, u, st);
      });
    },

    async cancelApplication(sess, appId, key) {
      await net();
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (!permissions(app, u, s).cancel) throw new ApiError('forbidden', 'Отозвать заявку на этом этапе нельзя');
        idem(s, key, appId, () => {
          s.jobs = s.jobs.filter((j) => j.appId !== appId);
          setStatus(app, 'CANCELLED');
          addEvent(app, { actor: 'client', actorName: u.name, client: 'Вы отозвали заявку', bank: 'Клиент отозвал заявку' });
        });
        return view(app, u, s);
      });
    },

    async uploadDocument(sess, appId, docId, file) {
      await net(300, 500);
      const u = userById(sess.userId);
      requireRole(u, ['owner', 'accountant'], 'Загружать документы');
      validateFile(file);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        const d = app.documents.find((x) => x.id === docId);
        if (!d) throw new ApiError('not_found', 'Запрос не найден');
        if (!['required', 'rejected', 'check', 'expired'].includes(d.status)) throw new ApiError('conflict', 'Документ уже на проверке');
        d.file = { ...file, uploadedAt: nowIso() };
        d.status = 'extracting';
        d.fields = [];
        d.extractError = undefined;
        d.rejectReason = undefined;
        schedule(s, { appId, type: 'ocr', docId, runAt: Date.now() + SOURCE_DELAY[modeOf(s, 'ocr')] + 600 });
        addEvent(app, { actor: 'client', actorName: u.name, client: `Вы загрузили файл «${file.name}»`, bank: `Клиент загрузил ${file.name}` });
        touch(app);
        return view(app, u, s);
      });
    },

    async confirmDocumentFields(sess, appId, docId, fields) {
      await net();
      const u = userById(sess.userId);
      if (fields.some((f) => !f.value.trim())) throw new ApiError('validation', 'Заполните все поля');
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        const d = app.documents.find((x) => x.id === docId)!;
        d.fields = fields.map((f) => ({ ...f, confirmed: true }));
        d.status = 'uploaded';
        touch(app);
        return view(app, u, s);
      });
    },

    async answerInfoRequest(sess, appId, docId, answer) {
      await net();
      const u = userById(sess.userId);
      if (!answer.trim()) throw new ApiError('validation', 'Напишите ответ');
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        const d = app.documents.find((x) => x.id === docId)!;
        d.answer = answer;
        d.status = 'uploaded';
        touch(app);
        return view(app, u, s);
      });
    },

    async sendDocuments(sess, appId, key) {
      await net(300, 500);
      const u = userById(sess.userId);
      requireRole(u, ['owner', 'accountant'], 'Отправлять документы');
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (s.idem[key] || app.status !== 'DOCS_REQUESTED') return view(app, u, s);
        const open = app.documents.filter((d) => ['required', 'rejected', 'expired', 'extracting', 'check'].includes(d.status));
        if (open.length) throw new ApiError('validation', 'Сначала загрузите и подтвердите все документы');
        idem(s, key, appId, () => {
          app.documents.forEach((d) => d.status === 'uploaded' && (d.status = 'review'));
          setStatus(app, 'DOCS_REVIEW');
          addEvent(app, { actor: 'client', actorName: u.name, client: 'Документы отправлены менеджеру. Они на проверке', bank: 'Клиент отправил документы на проверку' });
        });
        return view(app, u, s);
      });
    },

    async acceptOffer(sess, appId, offerId, version, key) {
      await net(300, 500);
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (s.idem[key]) return view(app, u, s);
        requireRole(u, ['owner'], 'Принять предложение');
        if (app.status !== 'OFFER' || !app.offer) throw new ApiError('conflict', 'Предложение уже неактуально — обновите страницу');
        if (app.offer.id !== offerId || app.offer.version !== version) throw new ApiError('conflict', 'Условия изменились. Посмотрите новую версию предложения', false);
        if (new Date(app.offer.validUntil).getTime() < Date.now()) throw new ApiError('expired', 'Срок действия предложения истёк');
        idem(s, key, appId, () => {
          app.offer!.acceptedAt = nowIso();
          app.offer!.acceptedBy = u.name;
          const participants = [{ name: u.name, role: 'Владелец, подписант', status: 'waiting' as const }];
          if (app.finance.guarantor !== 'none') participants.push({ name: app.finance.guarantor === 'owner' ? u.name : app.finance.guarantorName || 'Поручитель', role: 'Поручитель', status: 'waiting' as const });
          app.signing = { status: 'waiting', participants };
          setStatus(app, 'SIGNING');
          addEvent(app, { actor: 'client', actorName: u.name, client: `Вы приняли ${app.offer!.kind === 'counter' ? 'предложение банка' : 'условия'}: ${fmt(app.offer!.amount)} ₽ (версия ${app.offer!.version})`, bank: `Клиент принял оффер ${app.offer!.id} v${app.offer!.version}` });
        });
        return view(app, u, s);
      });
    },

    async rejectOffer(sess, appId, offerId, key) {
      await net();
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (s.idem[key]) return view(app, u, s);
        requireRole(u, ['owner'], 'Отказаться от предложения');
        if (app.status !== 'OFFER' || app.offer?.id !== offerId) throw new ApiError('conflict', 'Предложение уже неактуально');
        idem(s, key, appId, () => {
          setStatus(app, 'OFFER_REJECTED');
          addEvent(app, { actor: 'client', actorName: u.name, client: 'Вы отказались от предложения', bank: 'Клиент отказался от оффера' });
        });
        return view(app, u, s);
      });
    },

    async signContract(sess, appId, key) {
      await net(200, 400);
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        requireCompany(u, app);
        if (s.idem[key]) return view(app, u, s);
        if (u.role !== 'owner') throw new ApiError('forbidden', 'Подписать договор может только владелец (руководитель). Бухгалтер и наблюдатель — нет');
        if (app.status !== 'SIGNING' || !app.signing) throw new ApiError('conflict', 'Договор сейчас нельзя подписать');
        if (app.signing.status === 'signing' || app.signing.status === 'signed') return view(app, u, s);
        if (!app.offer || new Date(app.offer.validUntil).getTime() < Date.now()) throw new ApiError('expired', 'Срок действия предложения истёк — подписать нельзя');
        idem(s, key, appId, () => {
          app.signing!.status = 'signing';
          app.signing!.error = undefined;
          schedule(s, { appId, type: 'esign', runAt: Date.now() + SOURCE_DELAY[modeOf(s, 'esign')] + 800 });
          touch(app);
        });
        return view(app, u, s);
      });
    },

    // ───────── Банк ─────────

    async listTasks(sess) {
      await net(80, 160);
      const u = userById(sess.userId);
      if (!isBankRole(u.role)) throw new ApiError('forbidden', 'Только для сотрудников банка');
      const s = load();
      const tasks: BankTask[] = [];
      for (const app of s.apps) {
        const t = taskFor(app, s);
        if (!t) continue;
        const c = companyById(app.companyId);
        const waitingMin = Math.max(0, Math.round((Date.now() - new Date(app.statusSince).getTime()) / 60000));
        tasks.push({
          id: `task-${app.id}-${t.type}`,
          appId: app.id,
          number: app.number,
          companyName: c.name,
          inn: c.inn,
          product: app.product,
          amount: app.amount,
          type: t.type,
          role: t.role,
          appStatus: app.status,
          createdAt: app.statusSince,
          waitingMin,
          priority: app.amount > AUTO_LIMIT || waitingMin > 60 ? 'high' : 'normal',
          assignee: app.assignee?.name,
          category: app.scoring?.category,
          score: app.scoring?.score,
          actionable: t.actionable && t.role === u.role,
        });
      }
      return tasks.sort((a, b) => b.waitingMin - a.waitingMin);
    },

    async listAllApplications(sess) {
      await net(80, 160);
      const u = userById(sess.userId);
      if (!isBankRole(u.role)) throw new ApiError('forbidden', 'Только для сотрудников банка');
      return load().apps.filter((a) => a.status !== 'DRAFT').map(summary).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },

    async takeTask(sess, appId, key) {
      await net();
      const u = userById(sess.userId);
      return mutate((s) => {
        const app = getApp(s, appId);
        if (s.idem[key]) return view(app, u, s);
        const t = taskFor(app, s);
        if (!t || t.role !== u.role) throw new ApiError('forbidden', 'Эта задача не для вашей роли');
        if (!t.actionable) throw new ApiError('conflict', 'Сейчас по заявке ждём клиента — брать в работу нечего');
        idem(s, key, appId, () => {
          app.assignee = { userId: u.id, name: u.name, role: u.role as never, at: nowIso() };
          addEvent(app, { actor: 'bank', actorName: u.name, bank: `${u.name} (${roleName[u.role]}) взял(а) заявку в работу` });
          touch(app);
        });
        return view(app, u, s);
      });
    },

    async requestDocuments(sess, appId, req, key) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['manager', 'underwriter'], 'Запросить документы');
      if (!req.title.trim() || !req.why.trim() || !req.deadline) throw new ApiError('validation', 'Укажите, что нужно, зачем и срок');
      return mutate((s) => {
        const app = getApp(s, appId);
        if (s.idem[key]) return view(app, u, s);
        idem(s, key, appId, () => {
          createDocRequest(s, app, req, u.name);
          setStatus(app, 'DOCS_REQUESTED');
          addEvent(app, { actor: 'bank', actorName: u.name, client: `Банк попросил: ${req.title.toLowerCase()}. Это не отказ`, bank: `${u.name} запросил(а) документ: ${req.title}` });
        });
        return view(app, u, s);
      });
    },

    async reviewDocument(sess, appId, docId, verdict, reason) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['manager'], 'Проверять документы');
      if (verdict === 'reject' && !reason.trim()) throw new ApiError('validation', 'Укажите, что исправить');
      return mutate((s) => {
        const app = getApp(s, appId);
        const d = app.documents.find((x) => x.id === docId);
        if (!d) throw new ApiError('not_found', 'Документ не найден');
        if (d.status !== 'review') return view(app, u, s);
        if (verdict === 'accept') {
          d.status = 'accepted';
          addEvent(app, { actor: 'bank', actorName: u.name, client: `Документ «${d.title}» принят`, bank: `${u.name} принял(а) документ «${d.title}»` });
        } else {
          d.status = 'rejected';
          d.rejectReason = reason;
          addEvent(app, { actor: 'bank', actorName: u.name, client: `Документ «${d.title}» нужно исправить: ${reason}`, bank: `${u.name} вернул(а) документ: ${reason}` });
        }
        const pending = app.documents.some((x) => x.status === 'review');
        if (!pending) {
          if (app.documents.some((x) => x.status === 'rejected')) setStatus(app, 'DOCS_REQUESTED');
          else {
            app.round += 1;
            app.needsRescore = true;
            app.assignee = undefined;
            setStatus(app, 'SCORING');
            addEvent(app, { actor: 'system', actorName: 'Система', client: 'Документы приняты. Пересчитываем оценку с их учётом', bank: `Новый раунд рассмотрения №${app.round}: повторная оценка` });
            schedule(s, { appId, type: 'scoring', runAt: Date.now() + 1800 });
          }
        }
        touch(app);
        return view(app, u, s);
      });
    },

    async resolveCompliance(sess, appId, verdict, comment) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['compliance'], 'Решать по комплаенсу');
      return mutate((s) => {
        const app = getApp(s, appId);
        if (!app.checks.compliance?.match || app.complianceResolved) return view(app, u, s);
        app.complianceResolved = { verdict, by: u.name, at: nowIso() };
        app.checks.compliance = { ...app.checks.compliance, status: verdict === 'clear' ? 'ok' : 'warning', summary: verdict === 'clear' ? `Совпадение не подтверждено: ${comment || 'однофамилец'}` : 'Совпадение подтверждено', match: verdict === 'confirmed' };
        app.assignee = undefined;
        addEvent(app, { actor: 'bank', actorName: u.name, bank: `Комплаенс: ${verdict === 'clear' ? 'совпадение не подтверждено' : 'совпадение подтверждено'}${comment ? ' — ' + comment : ''}` });
        setStatus(app, 'SCORING');
        schedule(s, { appId, type: 'scoring', runAt: Date.now() + 1200 });
        return view(app, u, s);
      });
    },

    async escalateToCommittee(sess, appId) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['underwriter'], 'Передать на комитет');
      return mutate((s) => {
        const app = getApp(s, appId);
        if (app.committee) return view(app, u, s);
        app.committee = { requestedAt: nowIso(), by: u.name };
        addEvent(app, { actor: 'bank', actorName: u.name, client: 'Заявку рассмотрит кредитный комитет банка. Это не отказ', bank: `${u.name}: сумма выше лимита полномочий → кредитный комитет` });
        touch(app);
        return view(app, u, s);
      });
    },

    async makeDecision(sess, appId, input, key) {
      await net(300, 500);
      const u = userById(sess.userId);
      requireRole(u, ['underwriter'], 'Принять решение');
      return mutate((s) => {
        const app = getApp(s, appId);
        if (s.idem[key]) return view(app, u, s);
        const perm = permissions(app, u, s);
        if (app.decisionHistory.some((d) => d.round === app.round && d.by !== 'system')) throw new ApiError('conflict', 'Решение по этому раунду уже принято. Новое — только после новых данных');
        if (!perm.decide) throw new ApiError('forbidden', 'Решение сейчас недоступно: проверьте статус, проверки и комплаенс');
        if (app.assignee?.userId !== u.id) throw new ApiError('forbidden', 'Сначала возьмите заявку в работу');
        if (!input.aiTextChecked) throw new ApiError('validation', 'Проверьте текст для клиента и отметьте это');
        if (!input.clientText.trim()) throw new ApiError('validation', 'Нужен текст для клиента');
        const sc = app.scoring!;
        const byCommittee = !!app.committee;
        if (input.outcome === 'APPROVE' || input.outcome === 'COUNTER_OFFER') {
          const product = input.product ?? app.product;
          const p = productByCode(product);
          const amount = input.amount ?? app.amount;
          const term = input.termMonths ?? app.termMonths;
          if (amount < p.amountMin || amount > p.amountMax) throw new ApiError('validation', `Сумма вне диапазона продукта: ${fmt(p.amountMin)}–${fmt(p.amountMax)} ₽`);
          if (term < p.termMin || term > p.termMax) throw new ApiError('validation', `Срок вне диапазона продукта: ${p.termMin}–${p.termMax} мес`);
          const dscr = sc.cashFlow / (sc.currentPayments + monthlyPayment(product, amount, term));
          if (dscr < DSCR_MIN) throw new ApiError('validation', `DSCR при этих условиях ${dscr.toFixed(2).replace('.', ',')} — ниже ${String(DSCR_MIN).replace('.', ',')}. Уменьшите сумму или увеличьте срок`);
          if (amount > (u.authorityLimit ?? 0) && !byCommittee) throw new ApiError('authority', `Сумма выше вашего лимита полномочий (${fmt(u.authorityLimit ?? 0)} ₽). Передайте заявку на кредитный комитет`);
          const kind = input.outcome === 'APPROVE' && amount === app.amount && product === app.product && term === app.termMonths ? 'full' : 'counter';
          const dec: Decision = { id: id(s, 'dec'), round: app.round, outcome: kind === 'full' ? 'APPROVE' : 'COUNTER_OFFER', by: byCommittee ? 'committee' : 'underwriter', byName: byCommittee ? `Кредитный комитет (${u.name})` : u.name, at: nowIso(), reasons: input.reasons.map((r) => REASONS[r]).filter(Boolean), clientText: input.clientText, internalComment: input.internalComment, rulesVersion: RULES_VERSION, advice: [] };
          app.decision = dec;
          app.decisionHistory.unshift(dec);
          const guarantor = app.finance.guarantor === 'none' ? 'Не требуется' : app.finance.guarantor === 'owner' ? 'Владелец бизнеса' : app.finance.guarantorName || 'Третье лицо';
          app.offer = makeOffer({ id: id(s, 'of'), version: (app.offer?.version ?? 0) + 1, kind, product, amount, termMonths: term, requested: { product: app.product, amount: app.amount, termMonths: app.termMonths }, guarantor });
          setStatus(app, 'OFFER');
          addEvent(app, { actor: 'bank', actorName: dec.byName, client: kind === 'full' ? 'Банк одобрил заявку' : `Банк предложил другие условия: ${fmt(amount)} ₽`, bank: `${dec.byName}: ${dec.outcome}, ${fmt(amount)} ₽ на ${term} мес, DSCR ${dscr.toFixed(2).replace('.', ',')}` });
        } else if (input.outcome === 'REQUEST_DOCS') {
          if (!input.doc || !input.doc.title.trim() || !input.doc.why.trim() || !input.doc.deadline) throw new ApiError('validation', 'Для запроса документов заполните: что нужно, зачем, срок');
          const dec: Decision = { id: id(s, 'dec'), round: app.round, outcome: 'REQUEST_DOCS', by: 'underwriter', byName: u.name, at: nowIso(), reasons: input.reasons.map((r) => REASONS[r]).filter(Boolean), clientText: input.clientText, internalComment: input.internalComment, rulesVersion: RULES_VERSION, advice: [] };
          app.decisionHistory.unshift(dec);
          createDocRequest(s, app, input.doc, u.name);
          setStatus(app, 'DOCS_REQUESTED');
          addEvent(app, { actor: 'bank', actorName: u.name, client: `Банк попросил: ${input.doc.title.toLowerCase()}. Это не отказ`, bank: `${u.name}: запрос документов — ${input.doc.title}` });
        } else {
          const valid = input.reasons.filter((r) => REASONS[r]);
          if (!valid.length) throw new ApiError('validation', 'Для отказа выберите хотя бы одну допустимую причину');
          const dec: Decision = { id: id(s, 'dec'), round: app.round, outcome: 'DECLINE', by: byCommittee ? 'committee' : 'underwriter', byName: u.name, at: nowIso(), reasons: valid.map((r) => REASONS[r]), clientText: input.clientText, internalComment: input.internalComment, rulesVersion: RULES_VERSION, advice: adviceFor(valid, app) };
          app.decision = dec;
          app.decisionHistory.unshift(dec);
          setStatus(app, 'DECLINED');
          addEvent(app, { actor: 'bank', actorName: u.name, client: 'Банк не может выдать кредит по текущим данным. Причины — в решении', bank: `${u.name}: DECLINE (${valid.join(', ')})` });
        }
        idem(s, key, appId, () => undefined);
        app.assignee = undefined;
        return view(app, u, s);
      });
    },

    async rerunChecks(sess, appId) {
      await net();
      const u = userById(sess.userId);
      requireRole(u, ['manager', 'underwriter'], 'Перезапустить проверки');
      return mutate((s) => {
        const app = getApp(s, appId);
        const failed = CHECK_SOURCES.filter((c) => app.checks[c]?.status === 'waiting');
        failed.forEach((c) => {
          s.jobs = s.jobs.filter((j) => !(j.appId === appId && j.source === c));
          schedule(s, { appId, type: 'check', source: c, runAt: Date.now() + 300 });
        });
        addEvent(app, { actor: 'bank', actorName: u.name, bank: `${u.name}: повтор запросов (${failed.length})` });
        touch(app);
        return view(app, u, s);
      });
    },

    async draftClientText(sess, appId, outcome, reasons, amount) {
      const u = userById(sess.userId);
      requireRole(u, ['underwriter'], 'Готовить текст решения');
      const gate = await sourceGate('ai');
      await net(500, 900);
      if (gate !== 'OK') throw new ApiError('ai_unavailable', 'ИИ-помощник временно недоступен. Напишите текст вручную', true);
      const app = getApp(load(), appId);
      return draftDecisionText(outcome, reasons, amount ?? app.amount, app);
    },

    // ───────── Демо ─────────

    async getSources() {
      await net(40, 80);
      const s = load();
      return s.sources.map((x) => ({
        ...x,
        affected: s.apps
          .filter((a) => {
            if (a.checks[x.id]?.status === 'waiting') return true;
            if (x.id === 'abs' && a.disbursement?.status === 'checking') return true;
            if (x.id === 'esign' && a.signing?.status === 'error') return true;
            return false;
          })
          .map((a) => ({ id: a.id, number: a.number })),
      }));
    },

    async setSource(sid, patch) {
      await net(60, 120);
      mutate((s) => {
        const x = src(s, sid);
        const before = x.enabled ? x.mode : 'OFF';
        Object.assign(x, patch);
        const after = x.enabled ? x.mode : 'OFF';
        simLog(s, `${x.name}: ${before} → ${after}`, sid);
        if (x.enabled && (x.mode === 'SUCCESS' || x.mode === 'SLOW')) {
          // источник вернулся — повторяем ожидающие запросы сразу
          s.jobs.forEach((j) => {
            if ((j.type === 'check' && j.source === sid) || (sid === 'abs' && j.type === 'disburse')) j.runAt = Math.min(j.runAt, Date.now() + 500);
          });
        }
      });
      return this.getSources();
    },

    async getSimLog() {
      await net(40, 80);
      return load().simLog;
    },

    async runScenario(scenario) {
      await net(200, 300);
      return mutate((s) => {
        const map = {
          auto_approve: { company: 'A', input: { product: 'working_capital', goal: 'purchase', amount: 3_000_000, termMonths: 12, when: 'week' } },
          counter: { company: 'C', input: { product: 'working_capital', goal: 'purchase', amount: 5_000_000, termMonths: 18, when: 'week' } },
          decline: { company: 'E', input: { product: 'working_capital', goal: 'purchase', amount: 2_000_000, termMonths: 12, when: 'week' } },
          docs: { company: 'D', input: { product: 'overdraft', goal: 'cash_gap', amount: 600_000, termMonths: 6, when: 'month' } },
          source_fail: { company: 'A', input: { product: 'overdraft', goal: 'cash_gap', amount: 1_000_000, termMonths: 12, when: 'week' } },
        } as const;
        const sc = map[scenario];
        const owner = USERS.find((u) => u.companyId === sc.company && u.role === 'owner')!;
        if (scenario === 'source_fail') {
          const b = src(s, 'bki');
          b.mode = 'TIMEOUT';
          simLog(s, 'Сценарий: БКИ → TIMEOUT', 'bki');
        }
        const app = newApp(s, owner, { ...sc.input } as DraftInput);
        app.companyConfirmed = 'registry';
        app.finance.hasLoans = PROFILES[sc.company].currentPayments > 0;
        app.finance.loanPayments = PROFILES[sc.company].currentPayments || null;
        app.consents = { bki: { at: nowIso(), by: owner.name }, pd: { at: nowIso(), by: owner.name } };
        s.bkiConsents[sc.company] = s.bkiConsents[sc.company] ?? app.consents.bki!;
        s.apps.push(app);
        addEvent(app, { actor: 'system', actorName: 'Демо', bank: `Заявка создана сценарием «${scenario}»` });
        submitInternal(s, app, owner);
        simLog(s, `Сценарий «${scenario}»: создана заявка ${app.number} (${companyById(sc.company).name})`, undefined, app.id);
        return app.id;
      });
    },

    async resetDemo() {
      await net(200, 300);
      if (storageOk) {
        try {
          localStorage.removeItem(KEY);
        } catch {
          /* ignore */
        }
      }
      memory = null;
      cacheRaw = null;
      const fresh = seed();
      save(fresh);
      emit();
    },

    async askAi(sess, ctx: AiContext, question: string): Promise<AiAnswer> {
      const u = userById(sess.userId);
      await net(500, 900);
      const gate = await sourceGate('ai');
      mutate((s) => {
        const x = src(s, 'ai');
        x.lastCall = { at: nowIso(), result: gate === 'OK' ? 'SUCCESS' : gate, ms: SOURCE_DELAY[x.mode] };
      });
      if (gate !== 'OK') return { ok: false, text: '', sources: [], error: 'Помощник временно недоступен. Это не мешает заявке — все шаги можно пройти без него.' };
      const s = load();
      const app = ctx.appId ? s.apps.find((a) => a.id === ctx.appId) : undefined;
      const appView = app ? view(app, u, s) : undefined;
      const company = u.companyId ? companyById(u.companyId) : app ? companyById(app.companyId) : undefined;
      const chances = company ? s.chances[company.id] : undefined;
      return answerQuestion({ user: u, ctx, question, app: appView, company, chances, profile: company ? PROFILES[company.id] : undefined, bkiConsent: company ? !!s.bkiConsents[company.id] : false });
    },

    onChange(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
  };
}

export { maxAmountFor };
