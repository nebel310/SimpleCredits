import { describe, expect, it } from 'vitest';
import { money, months, monthsUpTo, pct, rate, short } from './format';

const plain = (s: string) => s.replace(/ /g, ' ');

describe('money', () => {
  it('целые рубли с пробелами и знаком ₽', () => {
    expect(plain(money(3_000_000))).toBe('3 000 000 ₽');
    expect(plain(money(65_000))).toBe('65 000 ₽');
    expect(plain(money(-600_000))).toBe('-600 000 ₽');
  });
  it('неразрывные пробелы — сумма не рвётся при переносе', () => {
    expect(money(65_000)).not.toMatch(/ /);
  });
  it('пустое значение — прочерк', () => {
    expect(money(null)).toBe('—');
    expect(money(undefined)).toBe('—');
  });
});

describe('short', () => {
  it('тысячи и миллионы без ошибок округления', () => {
    expect(plain(short(50_000))).toBe('50 тыс ₽');
    expect(plain(short(100_000))).toBe('100 тыс ₽');
    expect(plain(short(1_000_000))).toBe('1 млн ₽');
    expect(plain(short(1_250_000))).toBe('1,25 млн ₽');
    expect(plain(short(15_500_000))).toBe('15,5 млн ₽');
  });
  it('50 000 больше не превращается в «0,1 млн»', () => {
    expect(short(50_000)).not.toContain('0,1');
  });
  it('мелкие суммы — в рублях', () => {
    expect(plain(short(999))).toBe('999 ₽');
  });
});

describe('months', () => {
  it('склоняет слово «месяц»', () => {
    expect(months(1)).toBe('1 месяц');
    expect(months(3)).toBe('3 месяца');
    expect(months(12)).toBe('12 месяцев');
    expect(months(21)).toBe('21 месяц');
    expect(months(24)).toBe('24 месяца');
    expect(months(11)).toBe('11 месяцев');
  });
});

describe('monthsUpTo', () => {
  it('после «до» — родительный падеж', () => {
    expect(monthsUpTo(24)).toBe('24 месяцев');
    expect(monthsUpTo(12)).toBe('12 месяцев');
    expect(monthsUpTo(1)).toBe('1 месяца');
    expect(monthsUpTo(21)).toBe('21 месяца');
    expect(monthsUpTo(11)).toBe('11 месяцев');
  });
});

describe('pct', () => {
  it('запятая вместо точки', () => {
    expect(pct(2.83)).toBe('2,8%');
    expect(pct(15, 0)).toBe('15%');
  });
});

describe('rate', () => {
  it('ставка без округления: 17,5% не превращается в 18%', () => {
    expect(rate(17.5)).toBe('17,5%');
    expect(rate(18)).toBe('18%');
    expect(rate(20.8)).toBe('20,8%');
  });
});
