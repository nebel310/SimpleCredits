import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, type ApplicationView, type Session, type User } from '../../api';
import { useAction, useQuery, useSession } from '../../lib/hooks';
import { dateTime, money, time } from '../../lib/format';
import { BANK_STATUS, PRODUCT_NAME, ROLE_NAME, statusMeta, trackIndex } from '../../lib/status';
import { Btn, Chip, EmptyState, ErrorState, Loading, PageTitle, SelectField, Toggle, Tracker, toast } from '../../ui/kit';
import { COMPANY_SHORT } from '../../lib/companies';

export function Mirror() {
  const [params, setParams] = useSearchParams();
  const accounts = useQuery(() => api.getDemoAccounts(), [], { live: false });
  const manager = accounts.data?.users.find((u) => u.role === 'manager');
  const list = useQuery(() => (manager ? api.listAllApplications({ userId: manager.id }) : Promise.resolve([])), [manager?.id]);
  const appId = params.get('app') ?? list.data?.find((a) => !['ACTIVE', 'DECLINED'].includes(a.status))?.id ?? list.data?.[0]?.id;
  const [tech, setTech] = useState(false);

  if (accounts.error) return <ErrorState error={accounts.error} />;
  if (!accounts.data || !list.data) return <Loading lines={5} />;
  return (
    <>
      <PageTitle
        title="Одна заявка — две стороны"
        right={
          <div className="row-c" style={{ alignItems: 'flex-end' }}>
            <div style={{ minWidth: 340 }}>
              <SelectField label="Заявка" value={appId ?? ''} onChange={(v) => setParams({ app: v })} options={list.data.map((a) => ({ value: a.id, label: `№ ${a.number} · ${COMPANY_SHORT[a.companyId]} · ${BANK_STATUS[a.status]}` }))} />
            </div>
            <Toggle checked={tech} onChange={setTech} label="Технические детали" />
          </div>
        }
      />
      <p style={{ margin: 0 }} className="small muted">
        Слева кабинет клиента, справа кабинет банка. Действие с одной стороны сразу видно на другой: у заявки один идентификатор и одна актуальная версия. Новые заявки — на пульте источников.
      </p>
      {appId ? <MirrorPane key={appId} appId={appId} users={accounts.data.users} tech={tech} /> : <EmptyState title="Заявок пока нет" text="Создайте заявку сценарием на пульте источников." />}
    </>
  );
}

function bankUserFor(app: ApplicationView, users: User[]) {
  const complianceOpen = !!app.checks.compliance?.match && !app.complianceResolved;
  const role = app.status === 'MANUAL_REVIEW' ? (complianceOpen ? 'compliance' : 'underwriter') : 'manager';
  return users.find((u) => u.role === role)!;
}

function MirrorPane({ appId, users, tech }: { appId: string; users: User[]; tech: boolean }) {
  const nav = useNavigate();
  const login = useSession((s) => s.login);
  const owner0 = users.find((u) => u.role === 'owner');
  const [owner, setOwner] = useState<User | undefined>(undefined);
  const mgr = users.find((u) => u.role === 'manager')!;
  const bankQ = useQuery(() => api.getApplication({ userId: mgr.id }, appId), [appId]);
  const appB = bankQ.data;
  useEffect(() => {
    if (appB) setOwner(users.find((u) => u.companyId === appB.companyId && u.role === 'owner') ?? owner0);
  }, [appB?.companyId]); // eslint-disable-line react-hooks/exhaustive-deps
  const clientQ = useQuery(() => (owner ? api.getApplication({ userId: owner.id }, appId) : Promise.resolve(undefined)), [appId, owner?.id]);
  const appC = clientQ.data;
  const bankUser = appB ? bankUserFor(appB, users) : mgr;
  const bankS: Session = { userId: bankUser.id };
  const bankQ2 = useQuery(() => api.getApplication(bankS, appId), [appId, bankUser.id]);
  const appBank = bankQ2.data ?? appB;
  const lastShared = useMemo(() => appBank?.events.find((e) => e.client), [appBank]);

  // ───── действия клиента
  const clientAct = useAction(async (key) => {
    const s = { userId: owner!.id };
    const a = appC!;
    if (a.status === 'DOCS_REQUESTED') {
      const d = a.documents.find((x) => ['required', 'rejected', 'expired'].includes(x.status));
      if (d) {
        await api.uploadDocument(s, a.id, d.id, { name: 'vypiska_6m.pdf', size: 1_240_000, type: 'application/pdf' });
        return toast('Клиент загрузил выписку — ИИ распознаёт');
      }
      const c = a.documents.find((x) => x.status === 'check');
      if (c) {
        const fields = c.fields.map((f) => ({ ...f, value: f.value || (f.key === 'avg' ? '1 600 000 ₽' : f.key === 'total' ? '9 600 000 ₽' : f.key === 'bank' ? 'ПАО «Пример-Банк»' : '6 мес') }));
        await api.confirmDocumentFields(s, a.id, c.id, fields);
        return toast('Клиент подтвердил поля');
      }
      await api.sendDocuments(s, a.id, key);
      return toast('Документы отправлены менеджеру');
    }
    if (a.status === 'OFFER') {
      await api.acceptOffer(s, a.id, a.offer!.id, a.offer!.version, key);
      return toast('Клиент принял предложение');
    }
    if (a.status === 'SIGNING') {
      await api.signContract(s, a.id, key);
      return toast('Клиент подписывает договор');
    }
  });

  // ───── действия банка
  const bankAct = useAction(async (key) => {
    const a = appBank!;
    const s = bankS;
    if (a.permissions.takeTask) {
      await api.takeTask(s, a.id, key);
      return toast(`${bankUser.name} взял(а) заявку в работу`);
    }
    if (a.permissions.resolveCompliance) {
      await api.resolveCompliance(s, a.id, 'clear', 'однофамилец, дата рождения не совпадает');
      return toast('Комплаенс: совпадение не подтверждено');
    }
    if (a.permissions.reviewDocs) {
      for (const d of a.documents.filter((x) => x.status === 'review')) await api.reviewDocument(s, a.id, d.id, 'accept', '');
      return toast('Менеджер принял документ — повторная оценка');
    }
    if (a.permissions.decide && a.scoring) {
      const rec = a.scoring.recommendation;
      const amount = rec.amount ?? a.amount;
      if (amount > (bankUser.authorityLimit ?? 0) && !a.committee) {
        await api.escalateToCommittee(s, a.id);
        return toast('Передано на кредитный комитет');
      }
      const outcome = amount < a.amount ? 'COUNTER_OFFER' : 'APPROVE';
      const reasons = rec.reasonCodes.filter((r) => ['AFFORD', 'TREND', 'OVERDUE', 'DEBT_LOAD', 'LIMIT'].includes(r));
      let text: string;
      try {
        text = await api.draftClientText(s, a.id, outcome, reasons, amount);
      } catch {
        text = outcome === 'APPROVE' ? 'Банк одобрил заявку. Проверьте условия и подпишите договор в кабинете.' : `Мы готовы выдать ${money(amount)}. Если согласны — примите предложение в кабинете.`;
      }
      await api.makeDecision(s, a.id, { outcome, amount, termMonths: rec.termMonths ?? a.termMonths, product: a.product, reasons: outcome === 'COUNTER_OFFER' && !reasons.length ? ['AFFORD'] : reasons, clientText: text, internalComment: 'Решение по рекомендации правил (режим зеркала)', aiTextChecked: true }, key);
      return toast('Андеррайтер отправил решение');
    }
  });

  if (bankQ.error) return <ErrorState error={bankQ.error} />;
  if (!appC || !appBank) return <Loading lines={5} />;
  const m = statusMeta(appC);
  const clientLabel = appC.status === 'DOCS_REQUESTED' ? (appC.documents.some((x) => ['required', 'rejected', 'expired'].includes(x.status)) ? 'Загрузить выписку' : appC.documents.some((x) => x.status === 'check') ? 'Подтвердить поля' : appC.documents.some((x) => x.status === 'extracting') ? null : 'Отправить менеджеру') : appC.status === 'OFFER' ? `Принять ${money(appC.offer!.amount)}` : appC.status === 'SIGNING' && appC.signing?.status !== 'signing' ? 'Подписать договор' : null;
  const p = appBank.permissions;
  const bankLabel = p.takeTask ? 'Взять в работу' : p.resolveCompliance ? 'Совпадение не подтверждено' : p.reviewDocs ? 'Принять документ' : p.decide ? ((appBank.scoring?.recommendation.amount ?? appBank.amount) > (bankUser.authorityLimit ?? 0) && !appBank.committee ? 'Передать на кредитный комитет' : 'Решение по рекомендации правил') : null;

  return (
    <>
      {lastShared && (
        <div className="row-c" style={{ background: 'var(--c-lime)', color: 'var(--c-lime-ink)', padding: '12px 16px', borderRadius: 14 }}>
          <span style={{ width: 10, height: 10, background: 'var(--c-lime-ink)' }} />
          <b>{time(lastShared.at)}</b> {lastShared.client} — событие у обеих сторон
        </div>
      )}
      <div className="mirror">
        <section className="client">
          <div className="row-c between">
            <span className="caps">Клиент видит</span>
            <span className="xs muted">
              {COMPANY_SHORT[appC.companyId]} · {owner?.name}, владелец
            </span>
          </div>
          <div className="card">
            <Chip kind={m.chipClass}>{m.chip}</Chip>
            <b className="h3">{m.title}</b>
            <span className="small">
              {PRODUCT_NAME[appC.product]} · {money(appC.amount)} · {appC.termMonths} мес
            </span>
            <Tracker index={trackIndex(appC.status)} stop={['DECLINED'].includes(appC.status)} labels={['Отправлена', 'Проверка', 'Оценка', 'Решение', 'Подпись', 'Выдача']} />
            <div className="small">
              <b>Что нужно от вас:</b> {m.you}
            </div>
            <div className="btn-row">
              {clientLabel ? (
                <Btn view="accent" onClick={() => clientAct.run()} loading={clientAct.pending}>
                  {clientLabel}
                </Btn>
              ) : (
                <span className="xs muted">Сейчас действие за банком или системой</span>
              )}
              <button
                type="button"
                className="linkbtn muted"
                onClick={() => {
                  login(owner!);
                  nav(`/applications/${appC.id}`);
                }}
              >
                Открыть кабинет клиента →
              </button>
            </div>
            {clientAct.error && <ErrorState error={clientAct.error} />}
          </div>
          <div className="card tight">
            <span className="caps muted">Лента событий</span>
            <ul className="feed">
              {appC.events.slice(0, 6).map((e) => (
                <li key={e.id}>
                  <span className="t">{time(e.at)}</span>
                  <span className="dot" style={{ background: e.actor === 'bank' ? 'var(--c-red)' : e.actor === 'client' ? 'var(--c-black)' : 'var(--c-mid)' }} />
                  <span>{e.client}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
        <section className="bank">
          <div className="row-c between">
            <span className="caps">Банк видит</span>
            <span className="xs" style={{ color: '#babbc2' }}>
              {bankUser.name} · {ROLE_NAME[bankUser.role].toLowerCase()}
            </span>
          </div>
          <div className="card">
            <div className="row-c">
              <Chip kind="dark">{BANK_STATUS[appBank.status]}</Chip>
              {appBank.assignee && <Chip kind="mid">В работе: {appBank.assignee.name}</Chip>}
            </div>
            <b className="h3">
              Заявка {appBank.number} · {COMPANY_SHORT[appBank.companyId]}
            </b>
            {appBank.scoring && (
              <div className="grid-fields" style={{ gap: 8 }}>
                <div className="panel" style={{ padding: 12 }}>
                  <span className="xs muted">Балл</span>
                  <b>
                    {appBank.scoring.score} · {appBank.scoring.category}
                  </b>
                </div>
                <div className="panel" style={{ padding: 12 }}>
                  <span className="xs muted">Запрошено</span>
                  <b>{money(appBank.amount)}</b>
                </div>
                <div className="panel" style={{ padding: 12 }}>
                  <span className="xs muted">{appBank.offer ? 'Предложено' : 'Рекомендация'}</span>
                  <b>{appBank.offer ? money(appBank.offer.amount) : appBank.scoring.recommendation.amount ? money(appBank.scoring.recommendation.amount) : appBank.scoring.recommendation.outcome}</b>
                </div>
              </div>
            )}
            <div className="btn-row">
              {bankLabel ? (
                <Btn view="primary" onClick={() => bankAct.run()} loading={bankAct.pending}>
                  {bankLabel}
                </Btn>
              ) : (
                <span className="xs muted">Сейчас действие за клиентом или системой</span>
              )}
              <button
                type="button"
                className="linkbtn muted"
                onClick={() => {
                  login(bankUser);
                  nav(`/bank/applications/${appBank.id}`);
                }}
              >
                Открыть кабинет банка →
              </button>
            </div>
            {bankAct.error && <ErrorState error={bankAct.error} />}
          </div>
          <div className="card tight">
            <span className="caps muted">Журнал</span>
            <ul className="feed">
              {appBank.events.slice(0, 6).map((e) => (
                <li key={e.id}>
                  <span className="t">{time(e.at)}</span>
                  <span className="dot" style={{ background: e.actor === 'bank' ? 'var(--c-red)' : e.actor === 'client' ? 'var(--c-black)' : 'var(--c-mid)' }} />
                  <span>
                    <b>{e.actorName}:</b> {e.bank}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
      {tech && (
        <section className="card">
          <h2 className="h3">Технические детали</h2>
          <dl className="dl-grid">
            <div>
              <dt>application_id</dt>
              <dd>{appBank.id}</dd>
            </div>
            <div>
              <dt>status</dt>
              <dd>{appBank.status}</dd>
            </div>
            <div>
              <dt>version · round</dt>
              <dd>
                {appBank.version} · {appBank.round}
              </dd>
            </div>
            <div>
              <dt>offer</dt>
              <dd>{appBank.offer ? `${appBank.offer.id} v${appBank.offer.version}` : '—'}</dd>
            </div>
            <div>
              <dt>Обновлено</dt>
              <dd>{dateTime(appBank.updatedAt)}</dd>
            </div>
            <div>
              <dt>Событий</dt>
              <dd>{appBank.events.length}</dd>
            </div>
          </dl>
          <span className="xs muted">Действия идут с ключом идемпотентности: двойной клик не создаёт второго события.</span>
        </section>
      )}
      <section className="card">
        <h2 className="h3">Что показать жюри</h2>
        <div className="grid-3" style={{ gap: 12 }}>
          <div className="panel">
            <Chip kind="lime">1</Chip>
            <span className="small">Нажмите действие слева или справа — статус и лента сменятся у обеих сторон.</span>
          </div>
          <div className="panel">
            <Chip kind="lime">2</Chip>
            <span className="small">На пульте переключите БКИ в «Таймаут» и запустите сценарий — обе стороны увидят «ждём источник», а не отказ.</span>
          </div>
          <div className="panel">
            <Chip kind="lime">3</Chip>
            <span className="small">Дважды быстро нажмите «Принять» — версия заявки вырастет один раз, дубля не будет.</span>
          </div>
        </div>
      </section>
    </>
  );
}
