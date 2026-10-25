import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from './http';
import { useSession } from './session';
import { ApiError } from './types';

type Call = { url: string; init: RequestInit };
const calls: Call[] = [];

function respond(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function mockFetch(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return handler(url, init);
  }));
}

const auth = (c: Call) => (c.init.headers as Record<string, string>).Authorization;

beforeEach(() => {
  calls.length = 0;
  useSession.getState().clear();
});
afterEach(() => vi.unstubAllGlobals());

describe('request', () => {
  it('ходит на /api и ставит Bearer-токен', async () => {
    useSession.getState().setTokens('A1', 'R1');
    mockFetch(() => respond(200, { ok: true }));
    await request('GET', '/products');
    expect(calls[0].url).toBe('/api/products');
    expect(auth(calls[0])).toBe('Bearer A1');
  });

  it('без токена для auth:false', async () => {
    useSession.getState().setTokens('A1', 'R1');
    mockFetch(() => respond(200, {}));
    await request('POST', '/auth/login', { body: {}, auth: false });
    expect(auth(calls[0])).toBeUndefined();
  });

  it('собирает query и пропускает пустые значения', async () => {
    mockFetch(() => respond(200, {}));
    await request('GET', '/applications', { query: { cursor: null, limit: 50, x: '' } });
    expect(calls[0].url).toBe('/api/applications?limit=50');
  });

  it('текст ошибки бэкенда {detail} — как есть', async () => {
    mockFetch(() => respond(400, { detail: 'Пользователь с таким email уже существует' }));
    await expect(request('POST', '/auth/register', { auth: false })).rejects.toMatchObject({ status: 400, message: 'Пользователь с таким email уже существует' });
  });

  it('ошибка валидации 422 — список полей по-русски', async () => {
    mockFetch(() => respond(422, { detail: [{ loc: ['body', 'company', 'inn'], msg: 'too short' }, { loc: ['body', 'email'], msg: 'bad' }] }));
    await expect(request('PATCH', '/auth/me')).rejects.toMatchObject({ status: 422, message: 'Проверьте поля: ИНН, Email' });
  });

  it('502 без тела — понятный текст', async () => {
    mockFetch(() => new Response('', { status: 502 }));
    await expect(request('POST', '/applications')).rejects.toMatchObject({ status: 502, message: 'Сервис скоринга недоступен' });
  });

  it('нет сети — понятный текст', async () => {
    mockFetch(() => {
      throw new TypeError('Failed to fetch');
    });
    await expect(request('GET', '/products')).rejects.toBeInstanceOf(ApiError);
    await expect(request('GET', '/products')).rejects.toMatchObject({ status: 0, message: expect.stringContaining('Нет связи с сервером') });
  });

  it('401 → refresh → повтор запроса с новым токеном', async () => {
    useSession.getState().setTokens('OLD', 'R1');
    mockFetch((url, init) => {
      if (url.startsWith('/api/auth/refresh')) return respond(200, { access_token: 'NEW', token_type: 'bearer' });
      return (init.headers as Record<string, string>).Authorization === 'Bearer NEW' ? respond(200, { ok: 1 }) : respond(401, { detail: 'expired' });
    });
    await expect(request('GET', '/auth/me')).resolves.toEqual({ ok: 1 });
    expect(calls.map((c) => c.url)).toEqual(['/api/auth/me', '/api/auth/refresh?refresh_token=R1', '/api/auth/me']);
    expect(useSession.getState().access).toBe('NEW');
  });

  it('refresh не сработал, но это демо-аккаунт — входим заново', async () => {
    useSession.getState().setTokens('OLD', 'R1');
    useSession.getState().setDemo({ email: 'company-a@demo.simplecredits.ru', password: 'demo-a-2026' });
    mockFetch((url, init) => {
      if (url.startsWith('/api/auth/refresh')) return respond(400, { detail: 'Неверный refresh токен' });
      if (url === '/api/auth/login') return respond(200, { access_token: 'RELOGIN', refresh_token: 'R2' });
      return (init.headers as Record<string, string>).Authorization === 'Bearer RELOGIN' ? respond(200, { ok: 1 }) : respond(401, {});
    });
    await expect(request('GET', '/applications')).resolves.toEqual({ ok: 1 });
    expect(useSession.getState().refresh).toBe('R2');
  });

  it('продлить не вышло — сессия очищается', async () => {
    useSession.getState().setTokens('OLD', 'R1');
    mockFetch((url) => (url.startsWith('/api/auth/refresh') ? respond(400, {}) : respond(401, {})));
    await expect(request('GET', '/auth/me')).rejects.toMatchObject({ status: 401, message: 'Сессия истекла — войдите снова' });
    expect(useSession.getState().access).toBeNull();
  });

  it('одновременные 401 продлевают сессию один раз', async () => {
    useSession.getState().setTokens('OLD', 'R1');
    mockFetch((url, init) => {
      if (url.startsWith('/api/auth/refresh')) return respond(200, { access_token: 'NEW' });
      return (init.headers as Record<string, string>).Authorization === 'Bearer NEW' ? respond(200, {}) : respond(401, {});
    });
    await Promise.all([request('GET', '/a'), request('GET', '/b'), request('GET', '/c')]);
    expect(calls.filter((c) => c.url.startsWith('/api/auth/refresh'))).toHaveLength(1);
  });
});
