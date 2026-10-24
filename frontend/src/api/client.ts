import type {
  AiAnswer,
  AiContext,
  ApplicationSummary,
  ApplicationView,
  BankTask,
  ChancesResult,
  Company,
  DecisionInput,
  DemoAccounts,
  DocRequestInput,
  DraftInput,
  ExtractedField,
  Finance,
  Product,
  Session,
  SimLogEntry,
  SourceId,
  SourceState,
  User,
} from './types';

export interface LookupResult {
  status: 'found' | 'not_found' | 'unavailable' | 'invalid';
  company?: Company;
  message?: string;
  asOf?: string;
}

export interface FileInput {
  name: string;
  size: number;
  type: string;
}

/**
 * Контракт API кабинета. Все проверки прав, переходы статусов и решения —
 * на стороне сервера. Фронтенд только показывает то, что вернул сервер.
 * Методы, меняющие данные, принимают idempotencyKey — повторный вызов
 * с тем же ключом не создаёт второго действия.
 */
export interface CreditApi {
  readonly mode: 'mock' | 'http';

  // Демо-вход
  getDemoAccounts(): Promise<DemoAccounts>;
  getUser(s: Session): Promise<User>;
  getProducts(): Promise<Product[]>;

  // Клиент: главная
  getCompany(s: Session, companyId: string): Promise<Company>;
  getChances(s: Session, companyId: string, opts?: { refresh?: boolean }): Promise<ChancesResult>;
  giveBkiConsent(s: Session, companyId: string): Promise<void>;

  // Клиент: заявки
  listApplications(s: Session): Promise<ApplicationSummary[]>;
  getApplication(s: Session, id: string): Promise<ApplicationView>;
  createDraft(s: Session, input: DraftInput): Promise<ApplicationView>;
  updateDraft(s: Session, id: string, patch: Partial<DraftInput> & { finance?: Partial<Finance>; delegatedToAccountant?: boolean }): Promise<ApplicationView>;
  lookupCompany(s: Session, appId: string, inn: string): Promise<LookupResult>;
  confirmCompany(s: Session, appId: string, how: 'registry' | 'manual', note?: string): Promise<ApplicationView>;
  uploadStatement(s: Session, appId: string, file: FileInput): Promise<ApplicationView>;
  confirmStatementFields(s: Session, appId: string, fields: ExtractedField[]): Promise<ApplicationView>;
  removeStatement(s: Session, appId: string): Promise<ApplicationView>;
  giveConsents(s: Session, appId: string): Promise<ApplicationView>;
  submitApplication(s: Session, appId: string, idempotencyKey: string): Promise<ApplicationView>;
  cancelApplication(s: Session, appId: string, idempotencyKey: string): Promise<ApplicationView>;

  // Клиент: документы
  uploadDocument(s: Session, appId: string, docId: string, file: FileInput): Promise<ApplicationView>;
  confirmDocumentFields(s: Session, appId: string, docId: string, fields: ExtractedField[]): Promise<ApplicationView>;
  answerInfoRequest(s: Session, appId: string, docId: string, answer: string): Promise<ApplicationView>;
  sendDocuments(s: Session, appId: string, idempotencyKey: string): Promise<ApplicationView>;

  // Клиент: оффер, подпись
  acceptOffer(s: Session, appId: string, offerId: string, version: number, idempotencyKey: string): Promise<ApplicationView>;
  rejectOffer(s: Session, appId: string, offerId: string, idempotencyKey: string): Promise<ApplicationView>;
  signContract(s: Session, appId: string, idempotencyKey: string): Promise<ApplicationView>;

  // Банк
  listTasks(s: Session): Promise<BankTask[]>;
  listAllApplications(s: Session): Promise<ApplicationSummary[]>;
  takeTask(s: Session, appId: string, idempotencyKey: string): Promise<ApplicationView>;
  requestDocuments(s: Session, appId: string, req: DocRequestInput, idempotencyKey: string): Promise<ApplicationView>;
  reviewDocument(s: Session, appId: string, docId: string, verdict: 'accept' | 'reject', reason: string): Promise<ApplicationView>;
  resolveCompliance(s: Session, appId: string, verdict: 'clear' | 'confirmed', comment: string): Promise<ApplicationView>;
  escalateToCommittee(s: Session, appId: string): Promise<ApplicationView>;
  makeDecision(s: Session, appId: string, input: DecisionInput, idempotencyKey: string): Promise<ApplicationView>;
  rerunChecks(s: Session, appId: string): Promise<ApplicationView>;
  draftClientText(s: Session, appId: string, outcome: DecisionInput['outcome'], reasons: string[], amount?: number): Promise<string>;

  // Демо
  getSources(): Promise<SourceState[]>;
  setSource(id: SourceId, patch: Partial<Pick<SourceState, 'enabled' | 'mode'>>): Promise<SourceState[]>;
  getSimLog(): Promise<SimLogEntry[]>;
  runScenario(scenario: 'auto_approve' | 'counter' | 'decline' | 'docs' | 'source_fail'): Promise<string>;
  resetDemo(): Promise<void>;

  // ИИ-помощник (open-weights LLM на бэкенде; в моке — правила)
  askAi(s: Session, ctx: AiContext, question: string): Promise<AiAnswer>;

  /** Подписка на изменения (мок — мгновенно, HTTP — опрос/SSE) */
  onChange(cb: () => void): () => void;
}
