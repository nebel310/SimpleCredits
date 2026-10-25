// Типы повторяют Pydantic-схемы бэкенда (backend/schemas/*.py). Поля — как в API, без переименований.

export type Role = 'user' | 'admin';
export type ProductType = 'microloan' | 'term_loan' | 'overdraft' | 'credit_line' | 'leasing';
export type Purpose = 'working_capital' | 'equipment' | 'expansion' | 'refinancing' | 'other';
export type Segment = 'micro' | 'small';
export type LegalForm = 'llc' | 'individual_entrepreneur' | 'joint_stock_company';
export type RiskGrade = 'A' | 'B' | 'C' | 'D' | 'E';
export type Decision = 'approve' | 'approve_with_conditions' | 'manual_review' | 'decline';
export type AppStatus = 'pending' | 'failed' | 'confirmed' | 'different' | 'declined';

export interface Company {
  inn: string;
  ogrn: string;
  legal_name: string;
  legal_form: LegalForm;
  okved: string;
  region: string;
  registration_date: string;
  employee_count: number;
}

export interface Financials {
  annual_revenue_rub: number;
  annual_net_profit_rub: number;
  ebitda_rub: number;
  total_debt_rub: number;
  monthly_revenue_rub: number;
  monthly_expenses_rub: number;
  accounts_receivable_rub: number;
  cash_balance_rub: number;
  period_end: string;
}

export interface CreditHistory {
  active_obligations_count: number;
  total_outstanding_rub: number;
  monthly_debt_payments_rub: number;
  max_days_past_due_12m: number;
  has_current_past_due: boolean;
  credit_utilization: number;
  closed_obligations_count: number;
  applications_last_6m: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: Role;
  created_at: string;
  company: Company | null;
  financials: Financials | null;
  credit_history: CreditHistory | null;
}

export interface ProfileInput {
  username?: string;
  company?: Company;
  financials?: Financials;
  credit_history?: CreditHistory;
}

export interface Product {
  id: number;
  code: string;
  name: string;
  description: string;
  product_type: ProductType;
  segment: 'micro' | 'small' | 'both';
  min_amount_rub: number;
  max_amount_rub: number;
  min_term_months: number;
  max_term_months: number;
  rate_min_percent: number;
  rate_max_percent: number;
  purposes: Purpose[];
  features: string[];
  requirements: string[];
  extras: Record<string, unknown>;
  display_order: number;
}

export interface ReasonCode {
  code: string;
  description: string;
  feature: string;
  impact: 'positive' | 'negative' | 'neutral';
  contribution: number;
}

export interface DecisionCondition {
  code: string;
  description: string;
  recommended_amount_rub: number;
}

export interface DecisionResult {
  decision: Decision;
  reason_codes: string[];
  conditions: DecisionCondition[];
}

export interface ScoringResult {
  application_id: string;
  score: number;
  pd: number;
  risk_grade: RiskGrade;
  reason_codes: ReasonCode[];
  model_version: string;
  scored_at?: string | null;
  decision?: DecisionResult | null;
}

export interface Egrul {
  inn: string;
  ogrn: string;
  legal_name: string;
  legal_form: LegalForm;
  status: string;
  okved: string;
  okved_description: string;
  region: string;
  registration_date: string;
  employee_count: number;
  director: string;
  address: string;
}

export interface Fns {
  inn: string;
  tax_regime: string;
  tax_debt_rub: number;
  disqualified_persons: boolean;
  mass_address: boolean;
  mass_director: boolean;
  reliability_score: number;
  last_reporting_date: string;
}

export interface Bki extends CreditHistory {
  inn: string;
  credit_score: number;
  last_update: string;
}

export interface EnrichedData {
  egrul?: Egrul | null;
  fns?: Fns | null;
  bki?: Bki | null;
}

export interface ApplicationParams {
  product_type: ProductType;
  requested_amount_rub: number;
  term_months: number;
  purpose: Purpose;
  segment: Segment;
  submitted_at: string;
}

export interface Application {
  application_id: string;
  status: AppStatus;
  created_at: string;
  updated_at: string;
  application: ApplicationParams;
  company: Company;
  financials: Financials;
  credit_history: CreditHistory;
  scoring_result: ScoringResult | null;
  enriched_data: EnrichedData | null;
  explanation: string | null;
}

export interface ApplicationList {
  applications: Application[];
  next_cursor: string | null;
  previous_cursor: string | null;
}

export interface CreateApplicationInput {
  product_type: ProductType | null;
  requested_amount_rub: number;
  term_months: number;
  purpose: Purpose;
  segment: Segment;
}

export interface AppEvent {
  id: number;
  event_type: 'created' | 'enriched' | 'scored' | 'status_changed' | 'failed' | string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminStats {
  total: number;
  by_status: Record<string, number>;
  by_product_type: Record<string, number>;
  by_risk_grade: Record<string, number>;
  avg_score: number | null;
}

export interface ModelInfo {
  model_version: string;
  model_type: string;
  trained_at?: string | null;
  features: string[];
  metrics: Record<string, number>;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
}

/** Сообщения WebSocket /ws/applications (USERFLOW §8) */
export type WsMessage =
  | { type: 'status_changed'; application_id: string; status: AppStatus; payload: Record<string, unknown> | null; created_at: string }
  | { type: 'event'; application_id: string; event_type: string; payload: Record<string, unknown> | null; created_at: string };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
