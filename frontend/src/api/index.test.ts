import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './index';

const app = (id: string, created_at: string) => ({ application_id: id, created_at });

afterEach(() => vi.unstubAllGlobals());

describe('allApplications', () => {
  it('собирает все страницы по курсору и ставит новые заявки сверху', async () => {
    const pages: Record<string, unknown> = {
      '': { applications: [app('1', '2026-10-20T10:00:00Z'), app('2', '2026-10-21T10:00:00Z')], next_cursor: 'c2', previous_cursor: null },
      c2: { applications: [app('3', '2026-10-22T10:00:00Z')], next_cursor: null, previous_cursor: 'c1' },
    };
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      urls.push(url);
      const cursor = new URL(url, 'http://x').searchParams.get('cursor') ?? '';
      return new Response(JSON.stringify(pages[cursor]), { status: 200 });
    }));
    const list = await api.allApplications();
    expect(list.map((a) => a.application_id)).toEqual(['3', '2', '1']);
    expect(urls).toEqual(['/api/applications?limit=50', '/api/applications?cursor=c2&limit=50']);
  });

  it('не уходит в бесконечный цикл, если бэкенд всегда отдаёт курсор', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ applications: [], next_cursor: 'again', previous_cursor: null }), { status: 200 })));
    await api.allApplications();
    expect((fetch as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBe(20);
  });
});

describe('действия по заявке', () => {
  it('заявка уходит с ключом попытки Idempotency-Key', async () => {
    const seen: RequestInit[] = [];
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
      seen.push(init);
      return new Response(JSON.stringify({ application_id: 'x' }), { status: 201 });
    }));
    await api.createApplication({ product_type: null, requested_amount_rub: 500_000, term_months: 12, purpose: 'equipment', segment: 'micro' }, 'attempt-1');
    expect((seen[0].headers as Record<string, string>)['Idempotency-Key']).toBe('attempt-1');
  });

  it('принять, оформить, отказаться, повторить — POST на свои адреса', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      urls.push(`${init.method} ${url}`);
      return new Response(JSON.stringify({}), { status: 200 });
    }));
    await api.accept('a1');
    await api.issue('a1');
    await api.reject('a1');
    await api.retry('a1');
    await api.adminDecision('a1', { decision: 'decline' });
    expect(urls).toEqual(['POST /api/applications/a1/accept', 'POST /api/applications/a1/issue', 'POST /api/applications/a1/reject', 'POST /api/applications/a1/retry', 'POST /api/admin/applications/a1/decision']);
  });
});
