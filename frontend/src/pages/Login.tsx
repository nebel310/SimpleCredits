import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type User } from '../api';
import { useQuery, useSession } from '../lib/hooks';
import { ROLE_NAME } from '../lib/status';
import { Btn, Chip, ErrorState, Loading, SelectField } from '../ui/kit';
import { Px } from '../ui/Px';

const ROLE_HINT: Record<string, string> = {
  owner: 'Подаёт заявку, принимает предложение и подписывает договор',
  accountant: 'Заполняет финансы и загружает документы. Без права подписи и отправки',
  viewer: 'Видит статус заявки и решение, но не документы',
  manager: 'Проверяет документы, запрашивает недостающее',
  underwriter: 'Оценивает риск и принимает решение. Лимит полномочий — 5 млн ₽',
  compliance: 'Проверяет совпадения по перечням',
};

export function Login() {
  const q = useQuery(() => api.getDemoAccounts(), [], { live: false });
  const login = useSession((s) => s.login);
  const nav = useNavigate();
  const [company, setCompany] = useState('C');

  const enter = (u: User) => {
    login(u);
    nav(u.companyId ? '/home' : '/bank');
  };

  return (
    <main className="wrap page-main" id="main">
      <div className="row-c between">
        <div className="brand">
          <span className="logo-slot">ЛОГО</span>
          <span>Кредитный кабинет</span>
        </div>
        <span className="proto">Прототип · данные синтетические</span>
      </div>
      <section className="hero">
        <div style={{ flex: '1 1 560px', minWidth: 0 }}>
          <h1 style={{ fontSize: 36 }}>Вход для демо</h1>
          <p>Регистрация не нужна: выберите тестовый аккаунт и пройдите путь заявки за клиента или за банк. Все компании и данные выдуманы. В разных вкладках можно войти разными ролями — заявка обновится у всех сразу.</p>
        </div>
        <Px name="gem" size={98} color="var(--c-lime)" />
      </section>
      {q.error && <ErrorState error={q.error} onRetry={() => q.reload()} />}
      {!q.data ? (
        <Loading />
      ) : (
        <div className="grid-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(360px, 100%), 1fr))' }}>
          <section className="card">
            <div className="row-c between">
              <h2 className="h2">Клиент</h2>
              <Chip kind="high">Предприниматель</Chip>
            </div>
            <SelectField
              label="Тестовая компания"
              value={company}
              options={q.data.companies.map((c) => ({ value: c.id, label: `${c.name}` }))}
              onChange={setCompany}
              hint={q.data.companies.find((c) => c.id === company)?.scenario}
            />
            <div className="stack-s">
              {q.data.users
                .filter((u) => u.companyId === company)
                .map((u) => (
                  <div key={u.id} className="row-c" style={{ gap: 14, padding: '12px 0', borderTop: '1px solid var(--c-line)', flexWrap: 'nowrap' }}>
                    <span aria-hidden="true" style={{ width: 44, height: 44, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', background: u.role === 'owner' ? 'var(--c-black)' : 'var(--c-bg)', color: u.role === 'owner' ? 'var(--c-lime)' : 'var(--c-text)', fontWeight: 700 }}>
                      {ROLE_NAME[u.role].slice(0, 2).toUpperCase()}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>
                        {ROLE_NAME[u.role]} · {u.name}
                      </div>
                      <div className="small muted">{ROLE_HINT[u.role]}</div>
                    </div>
                    <Btn view={u.role === 'owner' ? 'primary' : 'outlined'} size={40} onClick={() => enter(u)}>
                      Войти
                    </Btn>
                  </div>
                ))}
              {q.data.users.filter((u) => u.companyId === company).length < 3 && <span className="xs muted">У этой компании в демо нет других ролей.</span>}
            </div>
          </section>
          <section className="card">
            <div className="row-c between">
              <h2 className="h2">Банк</h2>
              <Chip kind="mid">Сотрудник</Chip>
            </div>
            <div className="stack-s">
              {q.data.users
                .filter((u) => !u.companyId)
                .map((u, i) => (
                  <div key={u.id} className="row-c" style={{ gap: 14, padding: '12px 0', borderTop: i ? '1px solid var(--c-line)' : 0, flexWrap: 'nowrap' }}>
                    <span aria-hidden="true" style={{ width: 44, height: 44, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-bg)', fontWeight: 700 }}>
                      {ROLE_NAME[u.role].slice(0, 2).toUpperCase()}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>
                        {ROLE_NAME[u.role]} · {u.name}
                      </div>
                      <div className="small muted">{ROLE_HINT[u.role]}</div>
                    </div>
                    <Btn view="outlined" size={40} onClick={() => enter(u)}>
                      Войти
                    </Btn>
                  </div>
                ))}
            </div>
            <span className="xs muted">Роль сохраняется при переходах. Права проверяет сервер: скрытая кнопка — не единственная защита.</span>
          </section>
          <section className="card" style={{ background: 'var(--c-ai)', color: '#fff' }}>
            <div className="row-c between">
              <h2 className="h2">Демо для жюри</h2>
              <Chip kind="lime">Без роли</Chip>
            </div>
            <div className="stack">
              <div>
                <b>Пульт источников</b>
                <div className="small" style={{ color: '#ede5fb' }}>
                  Включает и ломает ФНС, БКИ, суды, подпись, выдачу и ИИ. Сценарии одной кнопкой.
                </div>
              </div>
              <div>
                <button type="button" className="btn-lime" onClick={() => nav('/demo/simulator')}>
                  Открыть пульт
                </button>
              </div>
              <div>
                <b>Режим зеркала</b>
                <div className="small" style={{ color: '#ede5fb' }}>
                  Клиент и банк на одном экране — видно, как одна заявка меняется у обоих
                </div>
              </div>
              <div>
                <button type="button" className="btn-lime" onClick={() => nav('/demo/mirror')}>
                  Открыть зеркало
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
