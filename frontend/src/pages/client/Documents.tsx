import { useEffect, useState } from 'react';
import { api, type ApplicationView } from '../../api';
import { useQuery, useSession } from '../../lib/hooks';
import { date } from '../../lib/format';
import { Btn, DocumentStatus, EmptyState, ErrorState, Loading, PageTitle, RoleGuard } from '../../ui/kit';
import { useAiScreen } from '../../ai/AiAssistant';

export function Documents() {
  const { session, user } = useSession();
  const list = useQuery(() => api.listApplications(session!), [session?.userId]);
  const [apps, setApps] = useState<ApplicationView[] | null>(null);
  useAiScreen('Документы', { chips: ['Какие документы понадобятся?'] });

  useEffect(() => {
    if (!list.data) return;
    Promise.all(list.data.filter((a) => a.status !== 'DRAFT').map((a) => api.getApplication(session!, a.id))).then(setApps).catch(() => setApps([]));
  }, [list.data, session]);

  if (user!.role === 'viewer')
    return (
      <>
        <PageTitle title="Документы" />
        <RoleGuard allowed={false} role={user!.role} what="Видеть документы">
          {null}
        </RoleGuard>
      </>
    );
  if (list.error) return <ErrorState error={list.error} onRetry={() => list.reload()} />;
  if (!apps) return <Loading />;
  const rows = apps.flatMap((a) => a.documents.map((d) => ({ a, d })));
  return (
    <>
      <PageTitle title="Документы" />
      <section className="card">
        {rows.length === 0 ? (
          <EmptyState title="Документов пока нет" text="Банк берёт данные из ФНС и выписки по счёту сам. Если понадобится документ, запрос появится здесь." />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Документ</th>
                  <th>Заявка</th>
                  <th>Срок</th>
                  <th>Статус</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map(({ a, d }) => (
                  <tr key={d.id}>
                    <td>
                      <b>{d.title}</b>
                      {d.file && <div className="xs muted">{d.file.name}</div>}
                    </td>
                    <td>№ {a.number}</td>
                    <td>{date(d.deadline)}</td>
                    <td>
                      <DocumentStatus status={d.status} />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Btn view="outlined" size={40} to={`/applications/${a.id}/documents`}>
                        Открыть
                      </Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
