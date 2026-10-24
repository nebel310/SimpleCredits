// HTTP-реализация API под реальный бэкенд. Эндпоинты описаны в docs/api-contract.md.
// Включается переменной окружения VITE_API_MODE=http (и VITE_API_URL).
import type { CreditApi } from './client';
import { ApiError, type Session } from './types';

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api';

async function call<T>(s: Session | null, method: string, path: string, body?: unknown, idem?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (s) headers['X-Demo-User'] = s.userId;
  if (idem) headers['Idempotency-Key'] = idem;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError('network', 'Нет связи с сервером. Данные сохранены — попробуйте ещё раз', true);
  }
  if (!res.ok) {
    let err: { code?: string; message?: string; retryable?: boolean } = {};
    try {
      err = await res.json();
    } catch {
      /* пусто */
    }
    throw new ApiError(err.code ?? `http_${res.status}`, err.message ?? 'Ошибка сервера', err.retryable ?? res.status >= 500);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

export function createHttpApi(): CreditApi {
  return {
    mode: 'http',
    getDemoAccounts: () => call(null, 'GET', '/demo/accounts'),
    getUser: (s) => call(s, 'GET', '/me'),
    getProducts: () => call(null, 'GET', '/products'),
    getCompany: (s, id) => call(s, 'GET', `/companies/${id}`),
    getChances: (s, id, o) => call(s, 'GET', `/companies/${id}/chances${o?.refresh ? '?refresh=1' : ''}`),
    giveBkiConsent: (s, id) => call(s, 'POST', `/companies/${id}/consents/bki`),
    listApplications: (s) => call(s, 'GET', '/applications'),
    getApplication: (s, id) => call(s, 'GET', `/applications/${id}`),
    createDraft: (s, input) => call(s, 'POST', '/applications', input),
    updateDraft: (s, id, patch) => call(s, 'PATCH', `/applications/${id}`, patch),
    lookupCompany: (s, id, inn) => call(s, 'POST', `/applications/${id}/company/lookup`, { inn }),
    confirmCompany: (s, id, how, note) => call(s, 'POST', `/applications/${id}/company/confirm`, { how, note }),
    uploadStatement: (s, id, f) => call(s, 'POST', `/applications/${id}/statement`, f),
    confirmStatementFields: (s, id, fields) => call(s, 'POST', `/applications/${id}/statement/confirm`, { fields }),
    removeStatement: (s, id) => call(s, 'DELETE', `/applications/${id}/statement`),
    giveConsents: (s, id) => call(s, 'POST', `/applications/${id}/consents`),
    submitApplication: (s, id, k) => call(s, 'POST', `/applications/${id}/submit`, {}, k),
    cancelApplication: (s, id, k) => call(s, 'POST', `/applications/${id}/cancel`, {}, k),
    uploadDocument: (s, id, doc, f) => call(s, 'POST', `/applications/${id}/documents/${doc}/file`, f),
    confirmDocumentFields: (s, id, doc, fields) => call(s, 'POST', `/applications/${id}/documents/${doc}/confirm`, { fields }),
    answerInfoRequest: (s, id, doc, answer) => call(s, 'POST', `/applications/${id}/documents/${doc}/answer`, { answer }),
    sendDocuments: (s, id, k) => call(s, 'POST', `/applications/${id}/documents/send`, {}, k),
    acceptOffer: (s, id, offerId, version, k) => call(s, 'POST', `/applications/${id}/offer/accept`, { offerId, version }, k),
    rejectOffer: (s, id, offerId, k) => call(s, 'POST', `/applications/${id}/offer/reject`, { offerId }, k),
    signContract: (s, id, k) => call(s, 'POST', `/applications/${id}/sign`, {}, k),
    listTasks: (s) => call(s, 'GET', '/bank/tasks'),
    listAllApplications: (s) => call(s, 'GET', '/bank/applications'),
    takeTask: (s, id, k) => call(s, 'POST', `/bank/applications/${id}/take`, {}, k),
    requestDocuments: (s, id, req, k) => call(s, 'POST', `/bank/applications/${id}/document-requests`, req, k),
    reviewDocument: (s, id, doc, verdict, reason) => call(s, 'POST', `/bank/applications/${id}/documents/${doc}/review`, { verdict, reason }),
    resolveCompliance: (s, id, verdict, comment) => call(s, 'POST', `/bank/applications/${id}/compliance`, { verdict, comment }),
    escalateToCommittee: (s, id) => call(s, 'POST', `/bank/applications/${id}/escalate`),
    makeDecision: (s, id, input, k) => call(s, 'POST', `/bank/applications/${id}/decision`, input, k),
    rerunChecks: (s, id) => call(s, 'POST', `/bank/applications/${id}/checks/rerun`),
    draftClientText: (s, id, outcome, reasons, amount) => call<{ text: string }>(s, 'POST', `/bank/applications/${id}/decision/draft-text`, { outcome, reasons, amount }).then((r) => r.text),
    getSources: () => call(null, 'GET', '/demo/sources'),
    setSource: (id, patch) => call(null, 'PATCH', `/demo/sources/${id}`, patch),
    getSimLog: () => call(null, 'GET', '/demo/log'),
    runScenario: (name) => call<{ applicationId: string }>(null, 'POST', `/demo/scenarios/${name}`).then((r) => r.applicationId),
    resetDemo: () => call(null, 'POST', '/demo/reset'),
    askAi: (s, ctx, question) => call(s, 'POST', '/ai/ask', { ctx, question }),
    onChange(cb) {
      listeners.add(cb);
      // Пока нет SSE — опрос раз в 3 секунды
      if (!timer) timer = setInterval(() => listeners.forEach((l) => l()), 3000);
      return () => {
        listeners.delete(cb);
        if (!listeners.size && timer) {
          clearInterval(timer);
          timer = null;
        }
      };
    },
  };
}
