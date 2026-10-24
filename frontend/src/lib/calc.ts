import { productByCode } from '../api/catalog';
import type { ProductCode } from '../api';

export function annuity(amount: number, ratePct: number, months: number): number {
  const r = ratePct / 100 / 12;
  return r === 0 ? amount / months : (amount * r) / (1 - Math.pow(1 + r, -months));
}

/** Нагрузка в месяц: кредит — аннуитет, овердрафт — проценты при среднем использовании 50% лимита */
export function monthlyLoad(product: ProductCode, amount: number, months: number) {
  const p = productByCode(product);
  return p.kind === 'limit' ? (amount * 0.5 * p.ratePct) / 100 / 12 : annuity(amount, p.ratePct, months);
}

/** Модельная стоимость использования лимита овердрафта */
export const overdraftCost = (used: number, days: number) => (used * productByCode('overdraft').ratePct * days) / 100 / 365;

export function termOptions(product: ProductCode) {
  const p = productByCode(product);
  const out: number[] = [];
  const step = p.termMax > 24 ? 12 : p.termMax > 12 ? 6 : 3;
  for (let t = p.termMin; t <= p.termMax; t += step) out.push(t);
  if (out[out.length - 1] !== p.termMax) out.push(p.termMax);
  return out;
}
