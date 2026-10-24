// Синтетические данные для демо. Все компании, люди и цифры выдуманы.
import type { Company, SourceId, SourceState, User } from '../types';

export const RULES_VERSION = 'demo-2026-10-v1';
/** До этой суммы система может одобрить без андеррайтера */
export const AUTO_LIMIT = 5_000_000;

export { PRODUCTS, GOALS, productByCode } from '../catalog';



export const COMPANIES: Company[] = [
  {
    id: 'A',
    type: 'IP',
    name: 'ИП Иванов А. С. («Компания A»)',
    inn: '771234567890',
    ogrn: '319774600123456',
    regDate: '2019-04-12',
    head: 'Иванов Андрей Сергеевич',
    employees: 8,
    okved: '47.19',
    okvedName: 'розничная торговля',
    address: 'г. Москва, ул. Тестовая, 5',
    scenario: 'Стабильные обороты → одобрение без участия банка',
  },
  {
    id: 'B',
    type: 'OOO',
    name: 'ООО «Компания B»',
    inn: '7701234560',
    ogrn: '1157746123450',
    regDate: '2015-02-03',
    head: 'Соколова Марина Игоревна',
    employees: 46,
    okved: '25.62',
    okvedName: 'обработка металлических изделий',
    address: 'Московская обл., г. Подольск, Промзона, 12',
    scenario: 'Крупная сумма и совпадение по комплаенсу → ручная проверка',
  },
  {
    id: 'C',
    type: 'OOO',
    name: 'ООО «Компания C»',
    inn: '7700000000',
    ogrn: '1227700000000',
    regDate: '2022-03-14',
    head: 'Смирнов Алексей Андреевич',
    employees: 12,
    okved: '46.90',
    okvedName: 'оптовая торговля',
    address: 'г. Москва, ул. Примерная, 1',
    scenario: 'Выручка падает → запрос выписки → встречное предложение',
  },
  {
    id: 'D',
    type: 'IP',
    name: 'ИП Ким Д. В. («Компания D»)',
    inn: '503198765432',
    ogrn: '326500000456789',
    regDate: '2026-05-20',
    head: 'Ким Дарья Викторовна',
    employees: 2,
    okved: '56.10',
    okvedName: 'кафе и рестораны',
    address: 'г. Химки, ул. Новая, 3',
    scenario: 'Молодой бизнес → не хватает данных',
  },
  {
    id: 'E',
    type: 'OOO',
    name: 'ООО «Компания E»',
    inn: '7709876543',
    ogrn: '1207700987654',
    regDate: '2020-09-01',
    head: 'Волков Евгений Петрович',
    employees: 20,
    okved: '41.20',
    okvedName: 'строительство зданий',
    address: 'г. Москва, ул. Строителей, 9',
    scenario: 'Долг перед налоговой → отказ с советами',
  },
];

export interface Profile {
  revenueYear: number | null;
  revenueAsOf: string;
  inflowsAvg: number;
  trendPct: number;
  cashFlow: number;
  currentPayments: number;
  weakMonths: number;
  taxDebt: number;
  overdueMaxDays: number;
  overdueNote: string;
  fsspSum: number;
  arbitrDefendant: number;
  arbitrNote: string;
  complianceMatch: boolean;
  bankYears: number;
  okvedRisk: 'low' | 'mid' | 'high';
  /** Что покажет выписка из другого банка (если её загрузят) */
  statement?: { otherBankInflows: number; trendPct: number; weakMonths: number; cashFlow: number };
}

export const PROFILES: Record<string, Profile> = {
  A: {
    revenueYear: 28_400_000,
    revenueAsOf: 'бухотчётность за 2025',
    inflowsAvg: 2_350_000,
    trendPct: 4,
    cashFlow: 850_000,
    currentPayments: 0,
    weakMonths: 0,
    taxDebt: 0,
    overdueMaxDays: 0,
    overdueNote: 'просрочек нет',
    fsspSum: 0,
    arbitrDefendant: 0,
    arbitrNote: 'дел нет',
    complianceMatch: false,
    bankYears: 3,
    okvedRisk: 'mid',
  },
  B: {
    revenueYear: 96_000_000,
    revenueAsOf: 'бухотчётность за 2025',
    inflowsAvg: 7_900_000,
    trendPct: 2,
    cashFlow: 1_600_000,
    currentPayments: 180_000,
    weakMonths: 1,
    taxDebt: 0,
    overdueMaxDays: 0,
    overdueNote: 'просрочек нет',
    fsspSum: 0,
    arbitrDefendant: 0,
    arbitrNote: '1 дело, компания — истец',
    complianceMatch: true,
    bankYears: 5,
    okvedRisk: 'mid',
  },
  C: {
    revenueYear: 42_000_000,
    revenueAsOf: 'бухотчётность за 2025',
    inflowsAvg: 3_500_000,
    trendPct: -18,
    cashFlow: 400_000,
    currentPayments: 50_000,
    weakMonths: 3,
    taxDebt: 0,
    overdueMaxDays: 31,
    overdueNote: 'просрочка 31 день, 03.2026',
    fsspSum: 0,
    arbitrDefendant: 1,
    arbitrNote: '1 дело, ответчик, 120 000 ₽',
    complianceMatch: false,
    bankYears: 2,
    okvedRisk: 'mid',
    statement: { otherBankInflows: 1_600_000, trendPct: -6, weakMonths: 3, cashFlow: 400_000 },
  },
  D: {
    revenueYear: null,
    revenueAsOf: 'отчётности ещё нет',
    inflowsAvg: 450_000,
    trendPct: 0,
    cashFlow: 90_000,
    currentPayments: 0,
    weakMonths: 0,
    taxDebt: 0,
    overdueMaxDays: 0,
    overdueNote: 'кредитной истории нет',
    fsspSum: 0,
    arbitrDefendant: 0,
    arbitrNote: 'дел нет',
    complianceMatch: false,
    bankYears: 0,
    okvedRisk: 'high',
  },
  E: {
    revenueYear: 35_000_000,
    revenueAsOf: 'бухотчётность за 2025',
    inflowsAvg: 2_900_000,
    trendPct: -9,
    cashFlow: 300_000,
    currentPayments: 120_000,
    weakMonths: 4,
    taxDebt: 74_000,
    overdueMaxDays: 96,
    overdueNote: 'просрочка 96 дней, 01.2026',
    fsspSum: 0,
    arbitrDefendant: 0,
    arbitrNote: 'дел нет',
    complianceMatch: false,
    bankYears: 1,
    okvedRisk: 'high',
  },
};

export const USERS: User[] = [
  { id: 'a-owner', name: 'Иванов А. С.', role: 'owner', companyId: 'A' },
  { id: 'a-acc', name: 'Белова Н. П.', role: 'accountant', companyId: 'A' },
  { id: 'b-owner', name: 'Соколова М. И.', role: 'owner', companyId: 'B' },
  { id: 'b-acc', name: 'Тихонов П. Р.', role: 'accountant', companyId: 'B' },
  { id: 'b-view', name: 'Зуев И. А.', role: 'viewer', companyId: 'B' },
  { id: 'c-owner', name: 'Смирнов А. А.', role: 'owner', companyId: 'C' },
  { id: 'c-acc', name: 'Иванова Е. В.', role: 'accountant', companyId: 'C' },
  { id: 'c-view', name: 'Лебедев О. Н.', role: 'viewer', companyId: 'C' },
  { id: 'd-owner', name: 'Ким Д. В.', role: 'owner', companyId: 'D' },
  { id: 'e-owner', name: 'Волков Е. П.', role: 'owner', companyId: 'E' },
  { id: 'e-acc', name: 'Орлова Т. С.', role: 'accountant', companyId: 'E' },
  { id: 'bank-manager', name: 'Иванов К. М.', role: 'manager' },
  { id: 'bank-uw', name: 'Петрова Е. В.', role: 'underwriter', authorityLimit: 5_000_000 },
  { id: 'bank-compliance', name: 'Гусев Р. А.', role: 'compliance' },
];

export const SOURCE_DEFS: { id: SourceId; name: string; description: string }[] = [
  { id: 'egrul', name: 'ФНС · ЕГРЮЛ/ЕГРИП', description: 'Реестр компаний и ИП' },
  { id: 'fns_tax', name: 'ФНС · налоги', description: 'Отчётность, недоимки, блокировки' },
  { id: 'bki', name: 'БКИ', description: 'Кредитная история' },
  { id: 'fssp', name: 'ФССП', description: 'Исполнительные производства' },
  { id: 'arbitr', name: 'Арбитраж', description: 'Судебные дела' },
  { id: 'compliance', name: 'Комплаенс', description: 'Проверка по перечням' },
  { id: 'ocr', name: 'Распознавание документов', description: 'Извлекает цифры из выписок' },
  { id: 'ai', name: 'ИИ-помощник', description: 'Open-weights LLM: объяснения' },
  { id: 'esign', name: 'Электронная подпись', description: 'Подписание договора в кабинете' },
  { id: 'abs', name: 'Выдача (АБС)', description: 'Перечисление денег на счёт' },
  { id: 'gateway', name: 'Приём заявок', description: 'Сохранение и отправка заявки' },
];

export const initialSources = (): SourceState[] =>
  SOURCE_DEFS.map((s) => ({ ...s, enabled: true, mode: 'SUCCESS' as const }));

export const SOURCE_DELAY: Record<string, number> = { SUCCESS: 700, SLOW: 3500, TIMEOUT: 2500, ERROR: 300 };
