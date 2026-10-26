import { useState } from 'react';
import { api, type Application, type BankDecisionInput } from '../../api';
import { useAction } from '../../lib/hooks';
import { dateTime, money } from '../../lib/format';
import { BANK_DECISION_NAME } from '../../lib/labels';
import { Btn, ErrorState, MoneyField, RadioGroup, TextField, toast } from '../../ui/kit';

type D = BankDecisionInput['decision'];

/** Форма решения сотрудника банка по заявке на ручной проверке */
export function BankDecisionForm({ a, onDone }: { a: Application; onDone: (updated: Application) => void }) {
  const [decision, setDecision] = useState<D>('approve');
  const [amount, setAmount] = useState<number | null>(null);
  const [comment, setComment] = useState('');
  const [tried, setTried] = useState(false);
  const requested = a.application.requested_amount_rub;

  const err = {
    amount: decision === 'approve_with_conditions' && (amount === null || amount <= 0 || amount >= requested) ? `Сумма меньше запрошенной — до ${money(requested - 1)}` : null,
    comment: comment.length > 1000 ? 'Не больше 1000 символов' : null,
  };
  const valid = !err.amount && !err.comment;

  const send = useAction(async () => {
    const updated = await api.adminDecision(a.application_id, {
      decision,
      recommended_amount_rub: decision === 'approve_with_conditions' ? amount : null,
      comment: comment.trim() || null,
    });
    toast('Решение сохранено — клиент увидит его в заявке');
    onDone(updated);
  });

  return (
    <section className="card" aria-label="Решение банка">
      <div className="stack-s">
        <h2 className="h2">Решение по заявке</h2>
        <span className="small muted">Модель отправила заявку на ручную проверку. Решение увидит клиент: при одобрении — с условиями и кнопкой «Принять предложение».</span>
      </div>
      <RadioGroup<D> name="bank-decision" value={decision} options={(Object.keys(BANK_DECISION_NAME) as D[]).map((d) => ({ value: d, label: BANK_DECISION_NAME[d] }))} onChange={setDecision} />
      {decision === 'approve_with_conditions' && (
        <MoneyField label="Сумма, которую одобряет банк" value={amount} onChange={setAmount} error={tried ? err.amount : null} hint="Если выбранный продукт на эту сумму не выдаётся, банк подберёт другой" />
      )}
      <TextField label="Комментарий для клиента" value={comment} onChange={setComment} error={err.comment} hint="Необязательно. Покажем клиенту как пояснение к решению" />
      {send.error && <ErrorState error={send.error} />}
      <div className="btn-row">
        <Btn
          view={decision === 'decline' ? 'primary' : 'accent'}
          loading={send.pending}
          onClick={() => {
            setTried(true);
            if (valid) send.run();
          }}
        >
          Сохранить решение
        </Btn>
      </div>
    </section>
  );
}

/** Что решил сотрудник банка — видят и клиент, и банк */
export function BankDecisionInfo({ a, bank }: { a: Application; bank?: boolean }) {
  const d = a.bank_decision!;
  return (
    <section className="card tight" aria-label="Решение сотрудника банка">
      <h2 className="h3">Решение сотрудника банка</h2>
      <dl className="dl">
        <div>
          <dt>Решение</dt>
          <dd>{BANK_DECISION_NAME[d.decision]}</dd>
        </div>
        {d.recommended_amount_rub ? (
          <div>
            <dt>Одобренная сумма</dt>
            <dd>{money(d.recommended_amount_rub)}</dd>
          </div>
        ) : null}
        {d.comment && (
          <div>
            <dt>Комментарий</dt>
            <dd>{d.comment}</dd>
          </div>
        )}
        <div>
          <dt>Когда</dt>
          <dd>{dateTime(d.decided_at ?? undefined)}</dd>
        </div>
        {bank && d.decided_by && (
          <div>
            <dt>Сотрудник</dt>
            <dd>{d.decided_by}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
