import type { CreditApi } from './client';
import { createHttpApi } from './http';
import { createMockApi } from './mock/server';

// VITE_API_MODE=http — работать с настоящим бэкендом, иначе мок в браузере
export const api: CreditApi = import.meta.env.VITE_API_MODE === 'http' ? createHttpApi() : createMockApi();

export * from './types';
export type { CreditApi, LookupResult, FileInput } from './client';
