import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, CHECK_SOURCES, type ApplicationView } from '../../api';
import { useAction, useQuery, useSession, useTick } from '../../lib/hooks';
import { ago, dateTime, money, time } from '../../lib/format';
import { PRODUCT_NAME, clientActionFor, statusMeta, trackIndex } from '../../lib/status';
import { AiHint, Btn, Chip, Confirm, DocumentStatus, EmptyState, ErrorState, Loading, PageTitle, StatusBanner, Tracker } from '../../ui/kit';
import { type PxName } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { productByCode } from '../../api/catalog';

const SRC_NAME: Record<string, string> = { egrul: 'Реестр ФНС', fns_tax: 'Налоги (ФНС)', bki: 'Кредитная история (БКИ)', fssp: 'Приставы (ФССП)', arbitr: 'Арбитражные суды', compliance: 'Проверка по перечням' };

export function ApplicationsList() {
  const { session } = useSession();
  const q = useQuery(() => api.listApplications(session!), [session?.userId]);
  useAiScreen('Мои заявки', { chips: ['Что сейчас происходит?', 'Какие документы понадобятся?'] });
  return (
    <>
      <PageTitle title="Заявки" right={<Btn view="accent" to="/apply/goal">Новая заявка</Btn>} />
      {q.error && <ErrorState error={q.error} onRetry={() => q.reload()} />}
      {!q.data ? (
        <Loading />
      ) : q.data.length === 0 ? (
        <section className="card">
          <EmptyState title="Заявок пока нет" text="Посмотрите шансы на главной и начните первую заявку — данные компании подтянем сами." action={<Btn view="accent" to="/apply/goal">Начать заявку</Btn>} />
        </section>
      ) : (
        <section className="card">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Заявка</th>
                  <th>Продукт и сумма</th>
                  <th>Статус</th>
                  <th>Обновлено</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {q.data.map((a) => {
                  const m = statusMeta(a as never);
                  return (
                    <tr key={a.id}>
                      <td>
                        <b>№ {a.number}</b>
                      </td>
                      <td>
                        {PRODUCT_NAME[a.product]}
                        <div className="xs muted">
                          {money(a.amount)} · {a.termMonths} мес
                        </div>
                      </td>
                      <td>
                        <Chip kind={m.chipClass}>{m.chip}</Chip>
                      </td>
                      <td className="small muted">{ago(a.updatedAt)}</td>
                      <td style={{ textAlign: 'right' }}>
                        <Btn view={a.status === 'DRAFT' ? 'primary' : 'outlined'} size={40} to={a.status === 'DRAFT' ? '/apply/goal' : `/applications/${a.id}`}>
                          {a.status === 'DRAFT' ? 'Продолжить' : 'Открыть'}
                        </Btn>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

export function useApp(id?: string) {
  const { session } = useSession();
  return useQuery(() => api.getApplication(session!, id!), [id, session?.userId]);
}

function bannerIcon(app: ApplicationView): PxName {
  switch (statusMeta(app).banner) {
    case 'success':
      return 'check';
    case 'action':
      return app.status === 'DOCS_REQUESTED' ? 'doc' : 'heart';
    case 'error':
    case 'decline':
      return 'alert';
    default:
      return 'wait';
  }
}

export function ApplicationCard() {
  const { id } = useParams();
  const { session } = useSession();
  const q = useApp(id);
  const [confirmCancel, setConfirmCancel] = useState(false);
  useTick(30000);
  const cancel = useAction(async (key) => {
    await api.cancelApplication(session!, id!, key);
    setConfirmCancel(false);
  });
  const app = q.data;
  useAiScreen('Карточка заявки', { appId: id, chips: ['Что сейчас происходит?', 'Это отказ?', 'Что мне делать дальше?'], tip: app && ['WAITING_SOURCE', 'MANUAL_REVIEW', 'DOCS_REQUESTED'].includes(app.status) ? { text: 'Объясню, что сейчас происходит с заявкой и нужно ли что-то от вас.', action: 'Что сейчас происходит?' } : undefined });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  if (!app) return <Loading lines={6} />;
  const m = statusMeta(app);
  const action = clientActionFor(app);
  const p = productByCode(app.product);
  const terminal = ['DECLINED', 'CANCELLED', 'OFFER_REJECTED', 'EXPIRED'].includes(app.status);
  const longWait = ['MANUAL_REVIEW', 'WAITING_SOURCE', 'DOCS_REVIEW'].includes(app.status);

  return (
    <>
      <PageTitle crumbs={`Заявки › № ${app.number}`} title={`${p.name} · ${money(app.amount)}`} right={<span className="small muted">Отправлена {dateTime(app.submittedBy?.at)} · {app.submittedBy?.name}</span>} />
      <StatusBanner
        kind={m.banner}
        icon={bannerIcon(app)}
        chip={<Chip kind={m.chipClass}>{m.chip}</Chip>}
        title={m.title}
        facts={[
          { label: 'Что происходит', value: m.what },
          { label: 'Кто сейчас работает', value: m.who },
          { label: 'Что нужно от вас', value: m.you },
        ]}
        actions={
          <>
            {action && app.permissions.seeDocuments !== false && (
              <Btn view="accent" to={action.to}>
                {action.label}
              </Btn>
            )}
            {action && !app.permissions.seeDocuments && action.to.includes('documents') && <span className="small muted">Документы видят владелец и бухгалтер</span>}
            {longWait && <span className="xs muted">Статус обновлён {ago(app.statusSince)}. Точный срок ручных и внешних проверок назвать нельзя — статус изменится здесь сам.</span>}
          </>
        }
      >
        {app.status === 'WAITING_SOURCE' && app.waitingFor && <span className="small">Ждём ответ: {SRC_NAME[app.waitingFor] ?? app.waitingFor}. Банк повторит запрос автоматически.</span>}
      </StatusBanner>

      <section className="card">
        <Tracker index={trackIndex(app.status)} stop={terminal && app.status !== 'CANCELLED'} labels={['Отправлена', 'Проверка данных', 'Оценка', 'Решение', 'Подписание', 'Выдача']} sub={app.status === 'DOCS_REQUESTED' ? 'ждём документ от вас' : app.status === 'WAITING_SOURCE' ? 'ждём источник' : app.status === 'MANUAL_REVIEW' ? 'дополнительная проверка' : undefined} />
      </section>

      <div className="row">
        <section className="card grow">
          <h2 className="h2">Лента событий</h2>
          {app.events.length === 0 ? (
            <EmptyState title="Событий пока нет" />
          ) : (
            <ul className="feed">
              {app.events.map((e) => (
                <li key={e.id}>
                  <span className="t">{time(e.at)}</span>
                  <span className="dot" style={{ background: e.actor === 'client' ? 'var(--c-black)' : e.actor === 'bank' ? 'var(--c-red)' : e.actor === 'source' ? 'var(--c-mid)' : 'var(--c-high)' }} aria-hidden="true" />
                  <span>
                    {e.client}
                    <span className="who-s" style={{ display: 'block' }}>
                      {e.actorName} · {dateTime(e.at)}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <aside className="side stack">
          <section className="card tight">
            <h2 className="h3">Что проверяем</h2>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {CHECK_SOURCES.map((s) => {
                const c = app.checks[s];
                const st = c?.status ?? 'pending';
                return (
                  <li key={s} className="row-c between small" style={{ flexWrap: 'nowrap' }}>
                    <span>{SRC_NAME[s]}</span>
                    {st === 'ok' || st === 'warning' ? (
                      <Chip kind="high">Готово</Chip>
                    ) : st === 'running' ? (
                      <Chip kind="mid">
                        <span className="spin" style={{ width: 10, height: 10, borderWidth: 2 }} /> Запрос
                      </Chip>
                    ) : st === 'waiting' ? (
                      <Chip kind="mid">Ждём ответ</Chip>
                    ) : (
                      <Chip kind="neutral">В очереди</Chip>
                    )}
                  </li>
                );
              })}
            </ul>
            <span className="xs muted">Подробности проверок видит банк. Ожидание ответа — не отказ.</span>
          </section>
          {app.documents.length > 0 && (
            <section className="card tight">
              <h2 className="h3">Документы</h2>
              {app.documents.map((d) => (
                <div key={d.id} className="row-c between small" style={{ flexWrap: 'nowrap' }}>
                  <span>{d.title}</span>
                  <DocumentStatus status={d.status} />
                </div>
              ))}
              {app.permissions.seeDocuments && (
                <Btn view="outlined" size={40} to={`/applications/${app.id}/documents`}>
                  Открыть запрос
                </Btn>
              )}
            </section>
          )}
          <section className="card tight">
            <h2 className="h3">Параметры</h2>
            <dl className="dl">
              <div>
                <dt>Продукт</dt>
                <dd>{p.name}</dd>
              </div>
              <div>
                <dt>{p.kind === 'limit' ? 'Лимит' : 'Сумма'}</dt>
                <dd>{money(app.amount)}</dd>
              </div>
              <div>
                <dt>Срок</dt>
                <dd>{app.termMonths} мес</dd>
              </div>
            </dl>
            {app.permissions.cancel && (
              <button type="button" className="linkbtn muted" style={{ alignSelf: 'flex-start' }} onClick={() => setConfirmCancel(true)}>
                Отозвать заявку
              </button>
            )}
          </section>
          {app.status === 'MANUAL_REVIEW' && <AiHint>Дополнительная проверка — обычная часть процесса для некоторых заявок. Если банку что-то понадобится, здесь появится запрос.</AiHint>}
        </aside>
      </div>

      <Confirm
        open={confirmCancel}
        title="Отозвать заявку?"
        text={<span>Рассмотрение остановится. Вернуть заявку нельзя, но можно подать новую.{cancel.error && <span className="err" style={{ display: 'block', marginTop: 8 }}>{cancel.error.message}</span>}</span>}
        confirm="Отозвать"
        danger
        pending={cancel.pending}
        onConfirm={() => cancel.run()}
        onClose={() => setConfirmCancel(false)}
      />
    </>
  );
}

