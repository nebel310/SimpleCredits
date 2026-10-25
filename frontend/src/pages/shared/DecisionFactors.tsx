import type { Application, ReasonCode } from '../../api';
import { dateTime, money, pct } from '../../lib/format';
import { CONDITION_NAME, DECISION_NAME, FEATURE_NOT_IN_APPLICATION, GRADE_KIND, POLICY_REASON, adviceFor, confirmedFactors, factorTitle, riskCategory } from '../../lib/labels';
import { Chip, Meter } from '../../ui/kit';

function FactorList({ items, bank }: { items: ReasonCode[]; bank?: boolean }) {
  const max = Math.max(0.0001, ...items.map((r) => Math.abs(r.contribution)));
  return (
    <ul className="factors">
      {items.map((r) => (
        <li key={r.code}>
          <div className="row-c between" style={{ flexWrap: 'nowrap' }}>
            <span>
              <b>{factorTitle(r)}</b>
              {bank && <span className="xs muted"> · {r.feature}</span>}
              {bank && FEATURE_NOT_IN_APPLICATION.has(r.feature) && <span className="xs muted"> · в заявке таких данных нет, модель взяла значение по умолчанию</span>}
            </span>
            <Chip kind={r.impact === 'positive' ? 'high' : r.impact === 'negative' ? 'low' : 'neutral'}>{r.impact === 'positive' ? 'снижает риск' : r.impact === 'negative' ? 'повышает риск' : 'нейтрально'}</Chip>
          </div>
          <span className="bar" aria-hidden="true">
            <span style={{ width: `${(Math.abs(r.contribution) / max) * 100}%`, background: r.impact === 'positive' ? 'var(--c-high)' : r.impact === 'negative' ? 'var(--c-negative)' : 'var(--c-gray)' }} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * «Что повлияло на решение» для клиента: категория риска, причины решения, подтверждённые факторы
 * (только посчитанные по данным заявки) и что делать дальше. Балл, PD и грейд клиенту не показываем.
 */
export function ClientFactors({ a }: { a: Application }) {
  const s = a.scoring_result;
  if (!s) return null;
  const reasons = s.decision?.reason_codes ?? [];
  const factors = confirmedFactors(s.reason_codes);
  const advice = adviceFor(a);
  const risk = riskCategory(s.risk_grade);
  const noProduct = reasons.includes('NO_SUITABLE_PRODUCT');
  return (
    <section className="card" aria-label="Что повлияло на решение">
      <div className="row-c between">
        <h2 className="h2">Что повлияло на решение</h2>
        {!noProduct && <Chip kind={risk.kind}>Категория: {risk.text}</Chip>}
      </div>
      {reasons.length > 0 && (
        <div className="stack-s">
          <b>Главные причины</b>
          <ul className="reasons">
            {reasons.map((r) => (
              <li key={r}>{POLICY_REASON[r] ?? 'Причина по правилам банка'}</li>
            ))}
          </ul>
        </div>
      )}
      {!noProduct && factors.length > 0 && (
        <div className="stack-s">
          <b>Факторы оценки</b>
          <span className="xs muted">Посчитаны по данным заявки — финансам компании и кредитной истории</span>
          <FactorList items={factors} />
        </div>
      )}
      {advice.length > 0 && (
        <div className="info-box">
          <b>Что делать дальше</b>
          <ul className="reasons" style={{ marginTop: 6 }}>
            {advice.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Полный результат скоринга для банка: балл, грейд, PD, решение модели, условия и все факторы */
export function BankScoring({ a }: { a: Application }) {
  const s = a.scoring_result;
  if (!s) return null;
  const dec = s.decision;
  const risk = riskCategory(s.risk_grade);
  return (
    <>
      <section className="card">
        <div className="row-c between">
          <h2 className="h2">Решение скоринга</h2>
          <span className="xs muted">
            Модель {s.model_version}
            {s.scored_at ? ` · ${dateTime(s.scored_at)}` : ''}
          </span>
        </div>
        <div className="kpis">
          <div className="kpi">
            <span className="muted small">Скоринговый балл</span>
            <b className="num" style={{ fontSize: 36 }}>
              {s.score}
              <span className="muted" style={{ fontSize: 16 }}> / 1000</span>
            </b>
            <Meter value={s.score / 10} color="var(--c-black)" />
          </div>
          <div className="kpi">
            <span className="muted small">Грейд риска</span>
            <b className="num" style={{ fontSize: 36 }}>
              {s.risk_grade}
            </b>
            <Chip kind={GRADE_KIND[s.risk_grade]}>{risk.text}</Chip>
          </div>
          <div className="kpi">
            <span className="muted small">Вероятность дефолта</span>
            <b className="num" style={{ fontSize: 36 }}>
              {pct(s.pd * 100)}
            </b>
            <span className="xs muted">оценка модели, PD</span>
          </div>
        </div>
        {dec && (
          <dl className="dl">
            <div>
              <dt>Решение</dt>
              <dd>{DECISION_NAME[dec.decision]}</dd>
            </div>
            {dec.reason_codes.map((r) => (
              <div key={r}>
                <dt>Причина</dt>
                <dd>
                  {POLICY_REASON[r] ?? r} <span className="xs muted">· {r}</span>
                </dd>
              </div>
            ))}
            {dec.conditions.map((c) => (
              <div key={c.code}>
                <dt>Условие · {CONDITION_NAME[c.code] ?? c.code}</dt>
                <dd>
                  {c.description}: {money(c.recommended_amount_rub)}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
      {s.reason_codes.length > 0 && (
        <section className="card">
          <h2 className="h2">Факторы модели</h2>
          <FactorList items={s.reason_codes} bank />
          <span className="xs muted">Клиент видит только факторы, посчитанные по данным заявки, — без балла, PD и грейда.</span>
        </section>
      )}
    </>
  );
}
