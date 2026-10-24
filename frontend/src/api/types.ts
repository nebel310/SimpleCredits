// Доменная модель кредитного кабинета.
// Эти типы — контракт между фронтендом и бэкендом. Мок-сервер (src/api/mock) и
// HTTP-клиент (src/api/http.ts) реализуют один и тот же интерфейс CreditApi.

export type ClientRole = 'owner' | 'accountant' | 'viewer';
export type BankRole = 'manager' | 'underwriter' | 'compliance';
export type Role = ClientRole | BankRole;

export const CLIENT_ROLES: ClientRole[] = ['owner', 'accountant', 'viewer'];
export const BANK_ROLES: BankRole[] = ['manager', 'underwriter', 'compliance'];
export const isBankRole = (r: Role): r is BankRole => (BANK_ROLES as Role[]).includes(r);

export interface User {
  id: string;
  name: string;
  role: Role;
  /** Для клиентских пользователей — компания */
  companyId?: string;
  /** Лимит полномочий андеррайтера, ₽ */
  authorityLimit?: number;
}

/** Сессия демо-входа. В проде — токен; сервер сам определяет роль по пользователю. */
export interface Session {
  userId: string;
}

export type ProductCode = 'working_capital' | 'overdraft' | 'development';
export type BusinessGoal = 'purchase' | 'cash_gap' | 'equipment' | 'gov_contract' | 'marketplace';

export interface Product {
  code: ProductCode;
  name: string;
  kind: 'loan' | 'limit';
  /** Для каких задач подходит — показываем на главной и в мастере */
  suits: string;
  amountMin: number;
  amountMax: number;
  termMin: number;
  termMax: number;
  /** Модельная ставка, % годовых — у каждого продукта своя */
  ratePct: number;
  /** Обязательные платежи (комиссии) */
  fees: { name: string; amount?: number; pct?: number }[];
  collateral: string;
}

export interface Company {
  id: string;
  type: 'IP' | 'OOO';
  name: string;
  inn: string;
  ogrn: string; // ОГРН или ОГРНИП
  regDate: string; // ISO
  head: string; // руководитель или ИП
  employees: number;
  okved: string;
  okvedName: string;
  address: string;
  /** Подпись сценария на экране входа */
  scenario: string;
}

// ───────── Внешние источники и симулятор ─────────

export type SourceId =
  | 'egrul'
  | 'fns_tax'
  | 'bki'
  | 'fssp'
  | 'arbitr'
  | 'compliance'
  | 'ocr'
  | 'ai'
  | 'esign'
  | 'abs'
  | 'gateway';

export type SourceMode = 'SUCCESS' | 'SLOW' | 'TIMEOUT' | 'ERROR';

export interface SourceState {
  id: SourceId;
  name: string;
  description: string;
  enabled: boolean;
  mode: SourceMode;
  lastCall?: { at: string; result: 'SUCCESS' | 'TIMEOUT' | 'ERROR'; ms: number; appId?: string };
  /** Заявки, которые сейчас ждут этот источник */
  affected?: { id: string; number: string }[];
}

/** Проверки, которые выполняются по заявке после отправки */
export const CHECK_SOURCES: SourceId[] = ['egrul', 'fns_tax', 'bki', 'fssp', 'arbitr', 'compliance'];

export type CheckStatus = 'pending' | 'running' | 'ok' | 'warning' | 'waiting' | 'failed';

export interface CheckResult {
  source: SourceId;
  status: CheckStatus;
  /** Краткий итог для банка */
  summary?: string;
  requestedAt?: string;
  answeredAt?: string;
  attempts: number;
  /** Совпадение по комплаенсу (реальный результат) — отличается от технической недоступности */
  match?: boolean;
}

// ───────── Заявка ─────────

export type AppStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'CHECKS'
  | 'WAITING_SOURCE'
  | 'SCORING'
  | 'MANUAL_REVIEW'
  | 'DOCS_REQUESTED'
  | 'DOCS_REVIEW'
  | 'OFFER'
  | 'SIGNING'
  | 'DISBURSEMENT'
  | 'ACTIVE'
  | 'REPAID'
  | 'DECLINED'
  | 'OFFER_REJECTED'
  | 'EXPIRED'
  | 'CANCELLED';

export type Outcome = 'APPROVE' | 'COUNTER_OFFER' | 'REQUEST_DOCS' | 'MANUAL_REVIEW' | 'DECLINE';

export type DataOrigin = 'bank' | 'registry' | 'client' | 'file';

export interface SourcedValue<T> {
  value: T | null;
  origin: DataOrigin;
  /** Источник словами: «ФНС, бухотчётность за 2025» */
  source: string;
  asOf?: string;
}

export interface FileRef {
  name: string;
  size: number;
  type: string;
  uploadedAt: string;
}

export type ExtractStatus = 'none' | 'uploading' | 'extracting' | 'check' | 'confirmed' | 'error';

export interface ExtractedField {
  key: string;
  label: string;
  value: string;
  confirmed: boolean;
}

export interface Finance {
  revenueYear: SourcedValue<number>;
  inflows3m: SourcedValue<number>; // среднемесячные поступления за 3 мес
  inflowTrendPct: SourcedValue<number>;
  hasLoans: boolean | null;
  loanPayments: number | null; // ₽ в месяц
  guarantor: 'none' | 'owner' | 'third_party';
  guarantorName: string;
  comment: string;
  statement?: { file: FileRef; status: ExtractStatus; fields: ExtractedField[]; error?: string };
}

export type DocStatus = 'required' | 'uploaded' | 'extracting' | 'check' | 'review' | 'accepted' | 'rejected' | 'expired';

export interface DocRequest {
  id: string;
  type: 'bank_statement' | 'tax_return' | 'contract' | 'info';
  title: string;
  why: string;
  requirements: string;
  formats: string[];
  maxSizeMb: number;
  deadline: string;
  requestedBy: string; // имя сотрудника или «Система»
  requestedAt: string;
  comment?: string;
  status: DocStatus;
  file?: FileRef;
  fields: ExtractedField[];
  extractError?: string;
  rejectReason?: string;
  /** Для типа info — текстовый ответ клиента */
  answer?: string;
}

export interface ScoreFactor {
  key: string;
  name: string;
  value: string;
  points: number;
  max: number;
  plain: string; // объяснение для клиента
}

export interface HardStop {
  code: string;
  text: string;
  plain: string;
  triggered: boolean;
}

export interface ScoringResult {
  id: string;
  round: number;
  at: string;
  rulesVersion: string;
  score: number;
  category: 'A' | 'B' | 'C' | 'D' | 'E';
  hardStops: HardStop[];
  factors: ScoreFactor[];
  dscr: number;
  debtLoadPct: number;
  monthlyPayment: number;
  cashFlow: number;
  currentPayments: number;
  recommendation: { outcome: Outcome; amount?: number; termMonths?: number; dscrAtAmount?: number; reasonCodes: string[] };
}

export interface Fee {
  name: string;
  amount: number;
}

export interface Offer {
  id: string;
  version: number;
  kind: 'full' | 'counter';
  product: ProductCode;
  amount: number;
  termMonths: number;
  ratePct: number;
  monthlyPayment: number; // для овердрафта — 0
  overpayment: number;
  fees: Fee[];
  collateral: string;
  guarantor: string;
  validUntil: string;
  requested: { product: ProductCode; amount: number; termMonths: number };
  acceptedAt?: string;
  acceptedBy?: string;
}

export interface Reason {
  code: string;
  bank: string; // формулировка для банка
  plain: string; // для клиента
}

export interface Decision {
  id: string;
  round: number;
  outcome: Outcome;
  by: 'system' | 'underwriter' | 'committee';
  byName: string;
  at: string;
  reasons: Reason[];
  clientText: string;
  internalComment?: string;
  rulesVersion: string;
  advice: string[]; // что можно сделать клиенту
}

export interface Participant {
  name: string;
  role: string;
  status: 'waiting' | 'signed' | 'not_required';
  at?: string;
}

export interface Signing {
  status: 'waiting' | 'signing' | 'signed' | 'error';
  error?: string;
  participants: Participant[];
  signedAt?: string;
}

export interface Payment {
  n: number;
  date: string;
  amount: number;
  principal: number;
  interest: number;
  status: 'scheduled' | 'paid' | 'overdue';
}

export interface Loan {
  product: ProductCode;
  amount: number; // сумма кредита или лимит
  used: number; // для овердрафта
  balance: number;
  ratePct: number;
  termMonths: number;
  schedule: Payment[];
  account: string;
}

export interface Disbursement {
  status: 'preparing' | 'checking' | 'done';
  attempts: number;
  operationId: string;
  doneAt?: string;
}

export type EventActor = 'client' | 'bank' | 'system' | 'source' | 'ai';

export interface AppEvent {
  id: string;
  at: string;
  actor: EventActor;
  actorName: string;
  /** Текст для клиента. Если нет — событие видит только банк */
  client?: string;
  /** Текст для банка (журнал) */
  bank: string;
  kind?: string;
}

export interface Application {
  id: string;
  number: string;
  companyId: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  /** Версия записи — растёт на каждое изменение (оптимистичная блокировка) */
  version: number;
  /** Раунд рассмотрения — растёт после новых документов/данных */
  round: number;
  product: ProductCode;
  goal: BusinessGoal;
  amount: number;
  termMonths: number;
  when: 'week' | 'month' | 'browsing';
  companyConfirmed: 'registry' | 'manual' | null;
  manualCompanyNote?: string;
  delegatedToAccountant: boolean;
  finance: Finance;
  consents: { bki?: { at: string; by: string }; pd?: { at: string; by: string } };
  status: AppStatus;
  statusSince: string;
  /** Какой источник ждём (для WAITING_SOURCE) */
  waitingFor?: SourceId;
  submittedBy?: { userId: string; name: string; role: Role; at: string };
  checks: Partial<Record<SourceId, CheckResult>>;
  scoring?: ScoringResult;
  scoringHistory: { id: string; round: number; at: string; score: number; category: string; trigger: string }[];
  documents: DocRequest[];
  decision?: Decision;
  decisionHistory: Decision[];
  offer?: Offer;
  signing?: Signing;
  disbursement?: Disbursement;
  loan?: Loan;
  assignee?: { userId: string; name: string; role: BankRole; at: string };
  committee?: { requestedAt: string; by: string };
  complianceResolved?: { verdict: 'clear' | 'confirmed'; by: string; at: string };
  needsRescore?: boolean;
  events: AppEvent[];
}

/** То, что видит конкретный пользователь (сервер фильтрует по роли) */
export interface ApplicationView extends Application {
  viewerRole: Role;
  permissions: Permissions;
  /** Чувствительные поля для банка (маскируются по роли) */
  sensitive?: { headPassport: string; headBirth: string };
  /** Клиенту — только цифры для «запаса прочности», без балла и версии правил */
  afford?: { cashFlow: number; currentPayments: number };
}

export interface Permissions {
  editDraft: boolean;
  submit: boolean;
  uploadDocs: boolean;
  seeDocuments: boolean;
  acceptOffer: boolean;
  sign: boolean;
  cancel: boolean;
  // банк
  takeTask: boolean;
  requestDocs: boolean;
  reviewDocs: boolean;
  decide: boolean;
  resolveCompliance: boolean;
  seeScoring: boolean;
}

export interface ApplicationSummary {
  id: string;
  number: string;
  companyId: string;
  companyName: string;
  product: ProductCode;
  amount: number;
  termMonths: number;
  status: AppStatus;
  statusSince: string;
  updatedAt: string;
  category?: string;
  score?: number;
  assignee?: string;
  offerAmount?: number;
}

export type TaskType = 'review' | 'documents' | 'compliance' | 'offer' | 'signing' | 'committee';

export interface BankTask {
  id: string;
  appId: string;
  number: string;
  companyName: string;
  inn: string;
  product: ProductCode;
  amount: number;
  type: TaskType;
  role: BankRole;
  appStatus: AppStatus;
  createdAt: string;
  waitingMin: number;
  priority: 'high' | 'normal';
  assignee?: string;
  category?: string;
  score?: number;
  /** Может ли текущий пользователь действовать по задаче */
  actionable: boolean;
}

// ───────── Главная: шансы ─────────

export type ChanceLevel = 'high' | 'mid' | 'low' | 'blocked' | 'unknown';

export interface ProductChance {
  product: ProductCode;
  level: ChanceLevel;
  /** null — не рассчитано */
  pct: number | null;
  approx: boolean;
  /** Предварительно доступная сумма */
  limit: number | null;
  blocker?: string;
  fits: boolean; // предварительно подходит под задачу
}

export interface ChanceFactor {
  key: string;
  dir: '+' | '-' | '?';
  name: string;
  note: string;
  source: string;
  asOf?: string;
}

export interface Recommendation {
  id: string;
  title: string;
  text: string;
  effect: string;
  action?: { label: string; kind: 'consent' | 'apply' | 'upload' | 'link'; product?: ProductCode };
}

export interface ChancesResult {
  state: 'ready' | 'insufficient' | 'error';
  calibrated: boolean;
  bkiConsent: boolean;
  calculatedAt: string;
  products: ProductChance[];
  factors: ChanceFactor[];
  recommendations: Recommendation[];
  error?: string;
}

// ───────── ИИ ─────────

export type AiMode = 'select' | 'free' | 'steps';

export interface AiContext {
  screen: string; // идентификатор раздела
  appId?: string;
  selection?: string;
}

export interface AiAnswer {
  ok: boolean;
  text: string;
  sources: { name: string; asOf?: string }[];
  actions?: { label: string; to: string }[];
  limited?: boolean; // действие/сведения недоступны роли
  error?: string;
}

// ───────── Ошибки API ─────────

export class ApiError extends Error {
  code: string;
  retryable: boolean;
  constructor(code: string, message: string, retryable = false) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

export interface DraftInput {
  product: ProductCode;
  goal: BusinessGoal;
  amount: number;
  termMonths: number;
  when: Application['when'];
}

export interface DecisionInput {
  outcome: 'APPROVE' | 'COUNTER_OFFER' | 'REQUEST_DOCS' | 'DECLINE';
  amount?: number;
  termMonths?: number;
  product?: ProductCode;
  reasons: string[];
  clientText: string;
  internalComment: string;
  doc?: { type: DocRequest['type']; title: string; why: string; deadline: string; comment: string };
  aiTextChecked: boolean;
}

export interface DocRequestInput {
  type: DocRequest['type'];
  title: string;
  why: string;
  deadline: string;
  comment: string;
}

export interface SimLogEntry {
  id: string;
  at: string;
  text: string;
  source?: SourceId;
  appId?: string;
}

export interface DemoAccounts {
  companies: Company[];
  users: User[];
}
