import { request } from './http';
import type {
  AdminStats,
  AppEvent,
  Application,
  ApplicationList,
  BankDecisionInput,
  Bki,
  CreateApplicationInput,
  Egrul,
  Fns,
  ModelInfo,
  Product,
  ProfileInput,
  Tokens,
  User,
} from './types';

export * from './types';
export { useSession, profileComplete } from './session';
export { API_URL, renewSession } from './http';

/** Бэкенд отдаёт заявки от старых к новым страницами по курсору. Собираем все страницы и ставим новые сверху */
async function collect(page: (cursor: string | null) => Promise<ApplicationList>, maxPages = 20): Promise<Application[]> {
  const out: Application[] = [];
  let cursor: string | null = null;
  for (let i = 0; i < maxPages; i++) {
    const r = await page(cursor);
    out.push(...r.applications);
    if (!r.next_cursor) break;
    cursor = r.next_cursor;
  }
  return out.sort((a, b) => b.created_at.localeCompare(a.created_at));
}

/** Все вызовы бэкенда в одном месте. Пути и тела — как в backend/webdoc.yaml */
export const api = {
  // Auth
  register: (username: string, email: string, password: string) =>
    request<{ success: boolean; user_id: number; message: string }>('POST', '/auth/register', {
      body: { username, email, password, password_confirm: password },
      auth: false,
    }),
  login: (email: string, password: string) => request<Tokens>('POST', '/auth/login', { body: { email, password }, auth: false }),
  logout: () => request<{ success: boolean }>('POST', '/auth/logout', { retry: false }),
  me: () => request<User>('GET', '/auth/me'),
  updateMe: (data: ProfileInput) => request<User>('PATCH', '/auth/me', { body: data }),

  // Каталог
  products: () => request<{ products: Product[] }>('GET', '/products', { auth: false }).then((r) => r.products),

  // Заявки
  /** idempotencyKey — один на попытку отправки: двойной клик и повтор сетью не создадут вторую заявку */
  createApplication: (data: CreateApplicationInput, idempotencyKey?: string) =>
    request<Application>('POST', '/applications', { body: data, headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined }),
  applications: (cursor?: string | null, limit = 50) => request<ApplicationList>('GET', '/applications', { query: { cursor, limit } }),
  allApplications: () => collect((c) => api.applications(c)),
  application: (id: string) => request<Application>('GET', `/applications/${id}`),
  events: (id: string) => request<AppEvent[]>('GET', `/applications/${id}/events`),
  accept: (id: string) => request<Application>('POST', `/applications/${id}/accept`),
  issue: (id: string) => request<Application>('POST', `/applications/${id}/issue`),
  reject: (id: string) => request<Application>('POST', `/applications/${id}/reject`),
  retry: (id: string) => request<Application>('POST', `/applications/${id}/retry`),

  // Администратор (роль admin)
  adminApplications: (cursor?: string | null, limit = 50) => request<ApplicationList>('GET', '/admin/applications', { query: { cursor, limit } }),
  allAdminApplications: () => collect((c) => api.adminApplications(c)),
  adminStats: () => request<AdminStats>('GET', '/admin/stats/overview'),
  adminDecision: (id: string, data: BankDecisionInput) => request<Application>('POST', `/admin/applications/${id}/decision`, { body: data }),
  modelInfo: () => request<ModelInfo>('GET', '/scoring/model-info'),

  // Мок-госуслуги бэкенда: подставить реквизиты и кредитную историю по ИНН
  egrul: (inn: string) => request<Egrul>('GET', `/mock/egrul/${inn}`, { auth: false }),
  fns: (inn: string) => request<Fns>('GET', `/mock/fns/${inn}`, { auth: false }),
  bki: (inn: string) => request<Bki>('GET', `/mock/bki/${inn}`, { auth: false }),
};
