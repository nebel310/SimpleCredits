import { ApiError, type Tokens } from './types';
import { useSession } from './session';

/** Адрес API. В Docker и при `npm run dev` это /api — запросы проксируются на бэкенд (порт 3001). */
export const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

const FIELD_LABEL: Record<string, string> = {
  email: 'Email',
  password: 'Пароль',
  password_confirm: 'Повтор пароля',
  username: 'Имя пользователя',
  inn: 'ИНН',
  ogrn: 'ОГРН',
  legal_name: 'Название',
  okved: 'ОКВЭД',
  region: 'Регион',
  registration_date: 'Дата регистрации',
  employee_count: 'Сотрудников',
  requested_amount_rub: 'Сумма',
  term_months: 'Срок',
  purpose: 'Цель',
  segment: 'Сегмент',
  credit_utilization: 'Использование лимитов',
};

const STATUS_TEXT: Record<number, string> = {
  401: 'Нужно войти заново',
  403: 'Недостаточно прав',
  404: 'Не найдено',
  500: 'Ошибка на сервере. Попробуйте ещё раз',
  502: 'Сервис оценки заявок недоступен',
  504: 'Сервис оценки заявок не ответил вовремя',
};

async function toError(res: Response): Promise<ApiError> {
  let body: Record<string, unknown> | undefined;
  try {
    body = await res.json();
  } catch {
    body = undefined;
  }
  const detail: unknown = body?.detail;
  if (typeof detail === 'string' && detail) return new ApiError(res.status, detail, body);
  if (Array.isArray(detail)) {
    // 422 от FastAPI: [{ loc: ['body', 'company', 'inn'], msg: '...' }]
    const fields = [...new Set(detail.map((d) => FIELD_LABEL[String(d?.loc?.[d.loc.length - 1])] ?? String(d?.loc?.[d.loc.length - 1] ?? '')).filter(Boolean))];
    return new ApiError(res.status, fields.length ? `Проверьте поля: ${fields.join(', ')}` : 'Проверьте заполненные поля');
  }
  return new ApiError(res.status, STATUS_TEXT[res.status] ?? `Ошибка ${res.status}`, body);
}

interface Opts {
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  auth?: boolean;
  retry?: boolean;
  headers?: Record<string, string>;
}

function url(path: string, query?: Opts['query']) {
  const qs = query
    ? Object.entries(query)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : '';
  return `${API_URL}${path}${qs ? `?${qs}` : ''}`;
}

export async function request<T>(method: string, path: string, opts: Opts = {}): Promise<T> {
  const { body, query, auth = true, retry = true } = opts;
  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = useSession.getState().access;
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(url(path, query), { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, 'Нет связи с сервером. Проверьте, что бэкенд запущен');
  }

  if (res.status === 401 && auth && retry) {
    if (await renewSession()) return request<T>(method, path, { ...opts, retry: false });
    useSession.getState().clear();
    throw new ApiError(401, 'Сессия истекла — войдите снова');
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ───── Продление сессии: refresh-токен, а для демо-аккаунта — повторный вход

let renewing: Promise<boolean> | null = null;

export function renewSession(): Promise<boolean> {
  if (!renewing) {
    renewing = (async () => {
      const s = useSession.getState();
      if (s.refresh) {
        try {
          // токен в теле, а не в адресе: адреса попадают в логи прокси
          const r = await request<{ access_token: string }>('POST', '/auth/refresh', { body: { refresh_token: s.refresh }, auth: false });
          useSession.getState().setTokens(r.access_token);
          return true;
        } catch {
          /* refresh не сработал — пробуем дальше */
        }
      }
      if (s.demo) {
        try {
          const t = await request<Tokens>('POST', '/auth/login', { body: s.demo, auth: false });
          useSession.getState().setTokens(t.access_token, t.refresh_token);
          return true;
        } catch {
          return false;
        }
      }
      return false;
    })().finally(() => {
      renewing = null;
    });
  }
  return renewing;
}
