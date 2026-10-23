import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type BankTask } from '../../api';
import { useAction, useQuery, useSession } from '../../lib/hooks';
import { ago, money, waitText } from '../../lib/format';
import { BANK_STATUS, PRODUCT_NAME, ROLE_NAME, TASK_NAME } from '../../lib/status';
import { Btn, Chip, EmptyState, ErrorState, Loading, PageTitle, toast } from '../../ui/kit';
import { useAiScreen } from '../../ai/AiAssistant';

export function Queue() {
  const { session, user } = useSession();
  const nav = useNavigate();
  const q = useQuery(() => api.listTasks(session!), [session?.userId]);
  const [scope, setScope] = useState<'mine' | 'all'>('mine');
  const [sort, setSort] = useState<'wait' | 'priority'>('wait');
  useAiScreen('Банк: очередь задач', { chips: ['Что такое комплаенс?', 'Что такое DSCR?'] });

  const take = useAction(async (key, t: BankTask) => {
    await api.takeTask(session!, t.appId, key);
    toast(`Заявка № ${t.number} у вас в работе`);
    nav(`/bank/applications/${t.appId}`);
  });

  const rows = useMemo(() => {
    const list = (q.data ?? []).filter((t) => scope === 'all' || t.role === user!.role);
    return [...list].sort((a, b) => (sort === 'priority' ? (a.priority === b.priority ? b.waitingMin - a.waitingMin : a.priority === 'high' ? -1 : 1) : b.waitingMin - a.waitingMin));
  }, [q.data, scope, sort, user]);

  const mineCount = (q.data ?? []).filter((t) => t.role === user!.role && t.actionable).length;

  return (
    <>
      <PageTitle
        title="Очередь задач"
        right={
          <div className="seg" role="group" aria-label="Какие задачи">
            <button type="button" aria-pressed={scope === 'mine'} onClick={() => setScope('mine')}>
              {ROLE_NAME[user!.role]} · {mineCount}
            </button>
            <button type="button" aria-pressed={scope === 'all'} onClick={() => setScope('all')}>
              Все роли · {q.data?.length ?? 0}
            </button>
          </div>
        }
      />
      {q.error && <ErrorState error={q.error} onRetry={() => q.reload()} />}
      {!q.data ? (
        <Loading lines={5} />
      ) : (
        <section className="card">
          <div className="row-c between">
            <span className="small muted">Задачи вашей роли можно взять в работу. Чужие — только посмотреть.</span>
            <div className="seg" role="group" aria-label="Сортировка">
              <button type="button" aria-pressed={sort === 'wait'} onClick={() => setSort('wait')}>
                Дольше ждут
              </button>
              <button type="button" aria-pressed={sort === 'priority'} onClick={() => setSort('priority')}>
                Приоритет
              </button>
            </div>
          </div>
          {rows.length === 0 ? (
            <EmptyState title="Задач нет" text={scope === 'mine' ? 'Для вашей роли сейчас ничего не ждёт. Новые задачи появятся здесь сами.' : 'Очередь пуста.'} />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Заявка</th>
                    <th>Компания</th>
                    <th>Продукт и сумма</th>
                    <th>Задача</th>
                    <th>Статус заявки</th>
                    <th>Риск</th>
                    <th>Ждёт</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => {
                    const mine = t.role === user!.role;
                    const myTask = t.assignee === user!.name;
                    return (
                      <tr key={t.id} className={mine && t.actionable && !t.assignee ? 'hl' : undefined}>
                        <td>
                          <b>{t.number}</b>
                          {t.priority === 'high' && (
                            <div>
                              <Chip kind="attention">Приоритет</Chip>
                            </div>
                          )}
                        </td>
                        <td>
                          {t.companyName}
                          <div className="xs muted">ИНН {t.inn}</div>
                        </td>
                        <td>
                          {PRODUCT_NAME[t.product]}
                          <div className="xs muted">{money(t.amount)}</div>
                        </td>
                        <td>
                          <b className="small">{TASK_NAME[t.type]}</b>
                          <div className="xs muted">{ROLE_NAME[t.role]}{t.assignee ? ` · ${t.assignee}` : ''}</div>
                        </td>
                        <td>
                          <Chip kind={t.actionable ? 'dark' : 'neutral'}>{BANK_STATUS[t.appStatus]}</Chip>
                        </td>
                        <td>{t.category ? <Chip kind={t.category <= 'B' ? 'high' : t.category === 'C' ? 'mid' : 'low'}>{t.category} · {t.score}</Chip> : '—'}</td>
                        <td className="small">{waitText(t.waitingMin)}</td>
                        <td style={{ textAlign: 'right' }}>
                          {mine && t.actionable && !t.assignee ? (
                            <Btn view="primary" size={40} onClick={() => take.run(t)} loading={take.pending}>
                              Взять в работу
                            </Btn>
                          ) : mine && t.actionable && myTask ? (
                            <Btn view="primary" size={40} to={`/bank/applications/${t.appId}`}>
                              Открыть
                            </Btn>
                          ) : (
                            <Btn view="outlined" size={40} to={`/bank/applications/${t.appId}`}>
                              Посмотреть
                            </Btn>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {take.error && <ErrorState error={take.error} />}
          <span className="xs muted">Маршрут зависит от категории, продукта, полноты данных и правил кредитной политики. Пороги прототипа — демонстрационные.</span>
        </section>
      )}
    </>
  );
}

export function AllApplications() {
  const { session } = useSession();
  const q = useQuery(() => api.listAllApplications(session!), [session?.userId]);
  useAiScreen('Банк: все заявки');
  return (
    <>
      <PageTitle title="Все заявки" />
      {q.error && <ErrorState error={q.error} onRetry={() => q.reload()} />}
      {!q.data ? (
        <Loading />
      ) : (
        <section className="card">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Заявка</th>
                  <th>Компания</th>
                  <th>Продукт и сумма</th>
                  <th>Статус</th>
                  <th>Риск</th>
                  <th>Обновлено</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {q.data.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <b>{a.number}</b>
                    </td>
                    <td>{a.companyName}</td>
                    <td>
                      {PRODUCT_NAME[a.product]}
                      <div className="xs muted">{money(a.amount)}</div>
                    </td>
                    <td>
                      <Chip kind="neutral">{BANK_STATUS[a.status]}</Chip>
                    </td>
                    <td>{a.category ? `${a.category} · ${a.score}` : '—'}</td>
                    <td className="small muted">{ago(a.updatedAt)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <Btn view="outlined" size={40} to={`/bank/applications/${a.id}`}>
                        Открыть
                      </Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
