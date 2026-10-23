import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, type DocRequest, type ExtractedField } from '../../api';
import { useAction, useSession } from '../../lib/hooks';
import { date, dateTime, time } from '../../lib/format';
import { AiHint, Btn, Chip, DocumentStatus, EmptyState, ErrorState, FileBox, FileDrop, Loading, PageTitle, RoleGuard, StatusBanner, TextField, toast } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { useApp } from './Applications';

export function DocsRequest() {
  const { id } = useParams();
  const { session, user } = useSession();
  const q = useApp(id);
  const app = q.data;
  const send = useAction(async (key) => {
    await api.sendDocuments(session!, id!, key);
    toast('Документы отправлены менеджеру');
  });
  useAiScreen('Запрос документов', { appId: id, chips: ['Какой нужен документ?', 'Это отказ?', 'Что если не успею?'], tip: { text: 'Подскажу, где взять выписку и в каком формате её загрузить.', action: 'Какой нужен документ?' } });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  if (!app) return <Loading lines={5} />;
  if (!app.permissions.seeDocuments)
    return (
      <>
        <PageTitle crumbs={`Заявки › № ${app.number}`} title="Запрос документов" />
        <RoleGuard allowed={false} role={user!.role} what="Видеть и загружать документы">
          {null}
        </RoleGuard>
      </>
    );

  const docs = app.documents;
  if (!docs.length)
    return (
      <>
        <PageTitle crumbs={`Заявки › № ${app.number}`} title="Документы" />
        <section className="card">
          <EmptyState title="Банк пока ничего не запрашивал" text="Если понадобится документ, запрос появится здесь и в карточке заявки." />
        </section>
      </>
    );

  const isInfo = docs.every((d) => d.type === 'info');
  const open = docs.filter((d) => ['required', 'rejected', 'expired', 'extracting', 'check'].includes(d.status));
  const ready = app.status === 'DOCS_REQUESTED' && open.length === 0 && docs.some((d) => d.status === 'uploaded');
  const underReview = app.status === 'DOCS_REVIEW';
  const deadline = docs.map((d) => d.deadline).sort()[0];
  const overdue = deadline && new Date(deadline).getTime() < Date.now() && app.status === 'DOCS_REQUESTED';

  return (
    <>
      <PageTitle crumbs={`Заявки › № ${app.number} › Запрос`} title={isInfo ? 'Уточните сведения' : docs.length > 1 ? 'Предоставьте документы' : 'Предоставьте документ'} />
      <StatusBanner
        kind={underReview ? 'wait' : app.status === 'DOCS_REQUESTED' ? 'action' : 'success'}
        icon={underReview ? 'wait' : app.status === 'DOCS_REQUESTED' ? 'doc' : 'check'}
        chip={<Chip kind={underReview ? 'mid' : app.status === 'DOCS_REQUESTED' ? 'attention' : 'high'}>{underReview ? 'На проверке у менеджера' : app.status === 'DOCS_REQUESTED' ? 'Нужно от вас' : 'Документы приняты'}</Chip>}
        title={underReview ? 'Документы на проверке' : app.status === 'DOCS_REQUESTED' ? docs.find((d) => d.status !== 'accepted')?.title ?? 'Документ' : 'Документы приняты — рассмотрение продолжается'}
        facts={[
          { label: 'Срок', value: deadline ? `до ${date(deadline)}` : '—' },
          { label: 'Запросил', value: docs[0].requestedBy },
          { label: 'Это отказ?', value: 'Нет. После проверки рассмотрение продолжится' },
        ]}
      >
        {overdue && <div className="warn-box" style={{ marginTop: 8 }}>Срок прошёл. Загрузите документ как можно скорее — менеджер увидит его в очереди.</div>}
      </StatusBanner>

      <div className="row">
        <div className="grow stack">
          {docs.map((d) => (
            <DocCard key={d.id} appId={app.id} d={d} canUpload={app.permissions.uploadDocs} />
          ))}
          {app.status === 'DOCS_REQUESTED' && (
            <section className="card tight">
              <div className="row-c between">
                <div>
                  <b>{ready ? 'Всё готово к отправке' : `Осталось: ${open.length}`}</b>
                  <div className="small muted">После отправки повторно отправить не получится — документы уйдут на проверку менеджеру.</div>
                </div>
                <Btn view="accent" onClick={() => send.run()} disabled={!ready || !app.permissions.uploadDocs} loading={send.pending}>
                  Отправить менеджеру
                </Btn>
              </div>
              {send.error && <ErrorState error={send.error} onRetry={() => send.run()} />}
            </section>
          )}
        </div>
        <aside className="side stack">
          <section className="card tight">
            <h2 className="h3">Зачем это банку</h2>
            <p style={{ margin: 0 }} className="small">
              {docs[0].why}
            </p>
            {docs[0].comment && <div className="info-box">Комментарий менеджера: {docs[0].comment}</div>}
          </section>
          <section className="card tight">
            <h2 className="h3">События</h2>
            <ul className="feed">
              {app.events.slice(0, 5).map((e) => (
                <li key={e.id}>
                  <span className="t">{time(e.at)}</span>
                  <span className="dot" style={{ background: e.actor === 'bank' ? 'var(--c-red)' : e.actor === 'client' ? 'var(--c-black)' : 'var(--c-high)' }} />
                  <span>{e.client}</span>
                </li>
              ))}
            </ul>
          </section>
          <AiHint>Выписку можно скачать в интернет-банке другого банка: раздел «Счета» → «Выписка» → период 6 месяцев → PDF или Excel. Цифры распознаю сам — вам останется проверить.</AiHint>
        </aside>
      </div>
    </>
  );
}

function DocCard({ appId, d, canUpload }: { appId: string; d: DocRequest; canUpload: boolean }) {
  const { session } = useSession();
  const [fields, setFields] = useState<ExtractedField[]>(d.fields);
  const [answer, setAnswer] = useState(d.answer ?? '');
  const [localErr, setLocalErr] = useState<string | null>(null);
  const [replace, setReplace] = useState(false);
  useEffect(() => setFields(d.fields), [d.status, d.fields.length]);

  const upload = useAction(async (_k, f: File) => {
    await api.uploadDocument(session!, appId, d.id, { name: f.name, size: f.size, type: f.type });
    setReplace(false);
  });
  const confirm = useAction(async () => {
    await api.confirmDocumentFields(session!, appId, d.id, fields);
    toast('Поля подтверждены');
  });
  const sendAnswer = useAction(async () => {
    await api.answerInfoRequest(session!, appId, d.id, answer);
  });

  const onFile = (f: File) => {
    setLocalErr(null);
    const ext = f.name.split('.').pop()?.toUpperCase() ?? '';
    if (!d.formats.includes(ext === 'JPEG' ? 'JPG' : ext === 'XLS' ? 'XLSX' : ext)) return setLocalErr(`Неподходящий формат. Подойдут: ${d.formats.join(', ')}`);
    if (f.size > d.maxSizeMb * 1024 * 1024) return setLocalErr(`Файл больше ${d.maxSizeMb} МБ`);
    upload.run(f);
  };

  const canEdit = canUpload && ['required', 'rejected', 'expired', 'check', 'uploaded'].includes(d.status);
  const showDrop = canUpload && (['required', 'rejected', 'expired'].includes(d.status) || replace) && d.type !== 'info';

  return (
    <section className="card">
      <div className="row-c between">
        <div className="row-c">
          <Px name="doc" size={24} color="var(--c-black)" />
          <h2 className="h3">{d.title}</h2>
        </div>
        <DocumentStatus status={d.status} />
      </div>
      <dl className="dl-grid">
        <div>
          <dt>Что нужно</dt>
          <dd style={{ fontWeight: 400 }}>{d.requirements}</dd>
        </div>
        {d.formats.length > 0 && (
          <div>
            <dt>Форматы</dt>
            <dd style={{ fontWeight: 400 }}>
              {d.formats.join(', ')} · до {d.maxSizeMb} МБ
            </dd>
          </div>
        )}
        <div>
          <dt>Срок</dt>
          <dd>до {date(d.deadline)}</dd>
        </div>
        <div>
          <dt>Запрошено</dt>
          <dd style={{ fontWeight: 400 }}>
            {d.requestedBy} · {dateTime(d.requestedAt)}
          </dd>
        </div>
      </dl>
      {d.status === 'rejected' && d.rejectReason && (
        <div className="err-box">
          <span>Менеджер вернул документ: {d.rejectReason}</span>
        </div>
      )}

      {d.type === 'info' ? (
        <div className="stack-s">
          <label className="field">
            <span className="lbl">Ваш ответ</span>
            <textarea className="native" value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={!canEdit} />
          </label>
          {canEdit && (
            <Btn view="primary" size={40} onClick={() => sendAnswer.run()} loading={sendAnswer.pending} disabled={answer.trim().length < 2}>
              Сохранить ответ
            </Btn>
          )}
        </div>
      ) : (
        <>
          {d.file && !replace && (
            <FileBox
              name={d.file.name}
              size={d.file.size}
              uploadedAt={d.file.uploadedAt}
              right={
                canEdit && d.status !== 'check' ? (
                  <button type="button" className="linkbtn muted" onClick={() => setReplace(true)}>
                    Заменить
                  </button>
                ) : undefined
              }
            />
          )}
          {showDrop && <FileDrop onFile={onFile} formats={d.formats} maxMb={d.maxSizeMb} disabled={upload.pending} label={d.status === 'rejected' ? 'Загрузите исправленный файл' : undefined} />}
          {upload.pending && (
            <div className="info-box">
              <span className="spin" style={{ width: 14, height: 14, marginRight: 8 }} /> Загружаем…
            </div>
          )}
          {(localErr || upload.error) && <ErrorState error={localErr ?? upload.error!} />}
          {d.status === 'extracting' && (
            <div className="ai-hint" style={{ padding: 16 }}>
              <div className="ttl">
                <span className="spin" style={{ width: 14, height: 14 }} /> ИИ распознаёт документ…
              </div>
            </div>
          )}
          {['check', 'uploaded', 'review', 'accepted'].includes(d.status) && fields.length > 0 && (
            <div className="ai-hint" style={{ padding: 18 }}>
              <div className="ttl">
                <Px name="gem" size={16} color="var(--c-ai)" />
                {d.extractError ? 'Не удалось распознать — заполните поля вручную' : d.status === 'check' ? 'ИИ распознал поля — проверьте' : 'Данные из документа'}
              </div>
              {d.extractError && <span className="small">{d.extractError}</span>}
              <div className="grid-fields">
                {fields.map((f, i) => (
                  <TextField key={f.key} label={f.label} value={f.value} disabled={d.status !== 'check'} onChange={(v) => setFields(fields.map((x, j) => (j === i ? { ...x, value: v } : x)))} hint={f.confirmed ? 'Подтверждено вами' : d.extractError ? 'Вы указали' : 'Из файла'} />
                ))}
              </div>
              {d.status === 'check' && canUpload && (
                <div className="btn-row">
                  <Btn view="primary" size={40} onClick={() => confirm.run()} loading={confirm.pending} disabled={fields.some((x) => !x.value.trim())}>
                    Всё верно, подтвердить
                  </Btn>
                  {confirm.error && <span className="xs" style={{ color: 'var(--c-negative-ink)' }}>{confirm.error.message}</span>}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
