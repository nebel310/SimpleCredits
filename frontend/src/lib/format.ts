export const money = (n: number | null | undefined, unit = ' ₽') =>
  n === null || n === undefined ? '—' : new Intl.NumberFormat('ru-RU').format(Math.round(n)).replace(/ /g, ' ') + unit;

export const mln = (n: number) => {
  const v = n / 1_000_000;
  return `${(Number.isInteger(v) ? v.toString() : v.toFixed(1)).replace('.', ',')} млн ₽`;
};

export const pct = (n: number, digits = 1) => `${n.toFixed(digits).replace('.', ',')}%`;
export const dec2 = (n: number) => n.toFixed(2).replace('.', ',');

export const date = (iso?: string) => (iso ? new Date(iso).toLocaleDateString('ru-RU') : '—');
export const time = (iso?: string) => (iso ? new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '—');
export const dateTime = (iso?: string) =>
  iso ? `${new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}, ${time(iso)}` : '—';

export function ago(iso?: string): string {
  if (!iso) return '—';
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return 'только что';
  if (min < 60) return `${min} мин назад`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} ч ${min % 60 ? (min % 60) + ' мин ' : ''}назад`;
  return date(iso);
}

export const waitText = (min: number) => (min < 60 ? `${min} мин` : `${Math.floor(min / 60)} ч ${min % 60 ? (min % 60) + ' мин' : ''}`.trim());

export const months = (n: number) => {
  const m10 = n % 10;
  const m100 = n % 100;
  const w = m10 === 1 && m100 !== 11 ? 'месяц' : [2, 3, 4].includes(m10) && ![12, 13, 14].includes(m100) ? 'месяца' : 'месяцев';
  return `${n} ${w}`;
};

export const newKey = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
