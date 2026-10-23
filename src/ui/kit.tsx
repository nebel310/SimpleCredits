import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button as AlfaButton } from '@alfalab/core-components-button';
import { Input } from '@alfalab/core-components-input';
import { Select } from '@alfalab/core-components-select';
import { Checkbox as AlfaCheckbox } from '@alfalab/core-components-checkbox';
import { Radio as AlfaRadio } from '@alfalab/core-components-radio';
import { Switch as AlfaSwitch } from '@alfalab/core-components-switch';
import type { ApiError, ChanceLevel, DataOrigin, DocStatus } from '../api';
import { Px, type PxName } from './Px';
import { TRACK, type BannerKind } from '../lib/status';

// ───── Кнопки (core-components Button) ─────

type BtnView = 'accent' | 'primary' | 'secondary' | 'outlined' | 'text' | 'transparent';

export function Btn({
  children,
  view = 'primary',
  onClick,
  to,
  disabled,
  loading,
  size = 48,
  block,
  type = 'button',
  title,
}: {
  children: ReactNode;
  view?: BtnView;
  onClick?: () => void;
  to?: string;
  disabled?: boolean;
  loading?: boolean;
  size?: 32 | 40 | 48 | 56;
  block?: boolean;
  type?: 'button' | 'submit';
  title?: string;
}) {
  const nav = useNavigate();
  const click = to ? () => nav(to) : onClick;
  return (
    <AlfaButton view={view} size={size} onClick={click} disabled={disabled} loading={loading} block={block} type={type} title={title}>
      {children}
    </AlfaButton>
  );
}

/** ActionButton: состояния loading / disabled (с причиной) / success / error */
export function ActionButton({
  children,
  onClick,
  pending,
  error,
  disabledReason,
  view = 'accent',
  done,
  doneText,
}: {
  children: ReactNode;
  onClick: () => void;
  pending?: boolean;
  error?: ApiError | null;
  disabledReason?: string | null;
  view?: BtnView;
  done?: boolean;
  doneText?: string;
}) {
  return (
    <div className="stack-s" style={{ alignItems: 'flex-start' }}>
      <Btn view={view} onClick={onClick} loading={pending} disabled={!!disabledReason || pending || (done && !!doneText)}>
        {done && doneText ? doneText : children}
      </Btn>
      {disabledReason && <span className="xs muted">{disabledReason}</span>}
      {error && <span className="xs" style={{ color: 'var(--c-negative-ink)', fontWeight: 600 }}>{error.message}</span>}
    </div>
  );
}

// ───── Поля ─────

export function TextField(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: ReactNode;
  error?: string | null;
  placeholder?: string;
  disabled?: boolean;
  inputMode?: 'numeric' | 'text';
  right?: ReactNode;
  id?: string;
}) {
  return (
    <Input
      label={props.label}
      labelView="outer"
      size={48}
      block
      value={props.value}
      onChange={(_, { value }) => props.onChange(value)}
      hint={props.error ? undefined : props.hint}
      error={props.error || undefined}
      placeholder={props.placeholder}
      disabled={props.disabled}
      inputMode={props.inputMode}
      rightAddons={props.right}
      id={props.id}
    />
  );
}

export function MoneyField(props: { label: string; value: number | null; onChange: (v: number | null) => void; hint?: ReactNode; error?: string | null; disabled?: boolean }) {
  const [text, setText] = useState(props.value === null ? '' : formatInt(props.value));
  useEffect(() => {
    const parsed = parseInt(text.replace(/\D/g, ''), 10);
    if ((isNaN(parsed) ? null : parsed) !== props.value) setText(props.value === null ? '' : formatInt(props.value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.value]);
  return (
    <TextField
      label={props.label}
      value={text}
      inputMode="numeric"
      onChange={(v) => {
        const digits = v.replace(/\D/g, '').slice(0, 10);
        setText(digits ? formatInt(Number(digits)) : '');
        props.onChange(digits ? Number(digits) : null);
      }}
      hint={props.hint}
      error={props.error}
      disabled={props.disabled}
      right={<span className="muted">₽</span>}
    />
  );
}

const formatInt = (n: number) => new Intl.NumberFormat('ru-RU').format(n).replace(/ /g, ' ');

export function SelectField<T extends string | number>(props: { label: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; hint?: string; error?: string | null; disabled?: boolean }) {
  return (
    <Select
      label={props.label}
      labelView="outer"
      size={48}
      block
      options={props.options.map((o) => ({ key: String(o.value), content: o.label }))}
      selected={String(props.value)}
      onChange={({ selected }) => {
        if (!selected) return;
        const o = props.options.find((x) => String(x.value) === selected.key);
        if (o) props.onChange(o.value);
      }}
      hint={props.error ? undefined : props.hint}
      error={props.error || undefined}
      disabled={props.disabled}
    />
  );
}

export function Check(props: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; hint?: ReactNode; disabled?: boolean }) {
  return <AlfaCheckbox checked={props.checked} onChange={(_, { checked }) => props.onChange(checked)} label={props.label} hint={props.hint} disabled={props.disabled} size={24} />;
}

export function RadioGroup<T extends string>(props: { name: string; value: T | null; options: { value: T; label: ReactNode; hint?: ReactNode }[]; onChange: (v: T) => void; disabled?: boolean; row?: boolean }) {
  return (
    <div role="radiogroup" className={props.row ? 'row-c' : 'stack-s'} style={props.row ? { gap: 24 } : undefined}>
      {props.options.map((o) => (
        <AlfaRadio key={o.value} name={props.name} label={o.label} hint={o.hint} checked={props.value === o.value} onChange={() => props.onChange(o.value)} disabled={props.disabled} size={24} />
      ))}
    </div>
  );
}

export function Toggle(props: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; disabled?: boolean }) {
  return <AlfaSwitch checked={props.checked} onChange={(_, { checked }) => props.onChange(checked)} label={props.label} disabled={props.disabled} />;
}

export function Field({ label, children, hint, error }: { label: string; children: ReactNode; hint?: ReactNode; error?: string | null }) {
  return (
    <div className="field">
      <span className="lbl">{label}</span>
      {children}
      {error ? <span className="err">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

// ───── Метки и показатели ─────

export function Chip({ kind = 'neutral', children }: { kind?: 'high' | 'mid' | 'low' | 'neutral' | 'dark' | 'lime' | 'ai' | 'attention'; children: ReactNode }) {
  return <span className={`chip ${kind}`}>{children}</span>;
}

export const LEVEL: Record<ChanceLevel, { label: string; fill: string; chip: 'high' | 'mid' | 'low' | 'neutral'; icon: PxName }> = {
  high: { label: 'Высокий шанс', fill: 'var(--c-high)', chip: 'high', icon: 'check' },
  mid: { label: 'Средний шанс', fill: 'var(--c-mid)', chip: 'mid', icon: 'up' },
  low: { label: 'Низкий шанс', fill: 'var(--c-negative)', chip: 'low', icon: 'alert' },
  blocked: { label: 'Сейчас недоступно', fill: 'var(--c-negative)', chip: 'low', icon: 'alert' },
  unknown: { label: 'Не рассчитано', fill: 'var(--c-gray)', chip: 'neutral', icon: 'wait' },
};

export function Meter({ value, color }: { value: number | null; color: string }) {
  const on = value === null ? 0 : Math.round(value / 10);
  return (
    <div className="meter" aria-hidden="true">
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} style={i < on ? { background: color } : undefined} />
      ))}
    </div>
  );
}

export function SourceTag({ origin, text }: { origin: DataOrigin; text?: string }) {
  const names: Record<DataOrigin, string> = { bank: 'Данные банка', registry: 'Реестр ФНС', client: 'Вы указали', file: 'Из файла' };
  return <span className={`src-tag ${origin}`}>{text ?? names[origin]}</span>;
}

export const DOC_STATUS: Record<DocStatus, { label: string; kind: 'high' | 'mid' | 'low' | 'neutral' | 'attention' }> = {
  required: { label: 'Требуется', kind: 'attention' },
  uploaded: { label: 'Загружен', kind: 'neutral' },
  extracting: { label: 'Распознаём', kind: 'mid' },
  check: { label: 'Проверьте поля', kind: 'attention' },
  review: { label: 'На проверке', kind: 'mid' },
  accepted: { label: 'Принят', kind: 'high' },
  rejected: { label: 'Исправить', kind: 'low' },
  expired: { label: 'Срок истёк', kind: 'low' },
};

export function DocumentStatus({ status }: { status: DocStatus }) {
  const m = DOC_STATUS[status];
  return <Chip kind={m.kind}>{m.label}</Chip>;
}

// ───── Трекер ─────

export function Tracker({ index, stop, waiting, labels = TRACK, sub }: { index: number; stop?: boolean; waiting?: boolean; labels?: string[]; sub?: string }) {
  return (
    <ol className="steps" style={{ gridTemplateColumns: `repeat(${labels.length}, minmax(0, 1fr))` }} aria-label="Этапы заявки">
      {labels.map((l, i) => {
        const cls = i < index ? 'done' : i === index ? (stop ? 'stop' : 'now') : '';
        return (
          <li key={l} className={cls} aria-current={i === index ? 'step' : undefined}>
            <span className="bar" aria-hidden="true" />
            {l}
            {i === index && sub && <span className="sub">{sub}</span>}
            {i === index && waiting && !sub && <span className="sub">сейчас</span>}
          </li>
        );
      })}
    </ol>
  );
}

// ───── StatusBanner ─────

export function StatusBanner({ kind, icon, chip, title, children, actions, facts }: { kind: BannerKind; icon?: PxName; chip?: ReactNode; title: ReactNode; children?: ReactNode; actions?: ReactNode; facts?: { label: string; value: ReactNode }[] }) {
  const color = kind === 'success' ? 'var(--c-high)' : kind === 'error' || kind === 'decline' ? 'var(--c-negative)' : kind === 'action' ? 'var(--c-red)' : kind === 'dark' ? 'var(--c-lime)' : 'var(--c-mid)';
  return (
    <section className={`banner ${kind}`} aria-live="polite">
      <div style={{ flex: '1 1 560px', minWidth: 0 }}>
        {chip}
        <h2 style={{ marginTop: chip ? 12 : 0 }}>{title}</h2>
        {children && <div style={{ marginTop: 8 }}>{children}</div>}
        {facts && (
          <div className="facts">
            {facts.map((f) => (
              <div key={f.label}>
                <span className="muted">{f.label}</span>
                <b>{f.value}</b>
              </div>
            ))}
          </div>
        )}
        {actions && <div className="btn-row" style={{ marginTop: 18 }}>{actions}</div>}
      </div>
      {icon && <Px name={icon} size={72} color={color} />}
    </section>
  );
}
