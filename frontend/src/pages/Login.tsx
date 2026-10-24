import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { profileComplete, useSession, type User } from '../api';
import { useAction } from '../lib/hooks';
import { signIn, signInAdmin, signInDemo, signUp } from '../lib/auth';
import { DEMO_ADMIN, DEMO_COMPANIES, type DemoCompany } from '../lib/demo';
import { Btn, Chip, ErrorState, TextField } from '../ui/kit';
import { Px } from '../ui/Px';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function Login() {
  const user = useSession((s) => s.user);
  const nav = useNavigate();
  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [username, setUsername] = useState('');
  const [tried, setTried] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const go = (u: User) => nav(u.role === 'admin' ? '/bank' : profileComplete(u) ? '/home' : '/profile', { replace: true });

  const form = useAction(async () => {
    const u = tab === 'login' ? await signIn(email.trim(), password) : await signUp(username.trim(), email.trim(), password);
    go(u);
  });
  const demo = useAction(async (d: DemoCompany | 'admin') => {
    setBusyKey(d === 'admin' ? 'admin' : d.key);
    try {
      go(d === 'admin' ? await signInAdmin() : await signInDemo(d));
    } finally {
      setBusyKey(null);
    }
  });

  if (user) return <Navigate to={user.role === 'admin' ? '/bank' : '/home'} replace />;

  const errors = {
    username: tab === 'register' && !username.trim() ? 'Укажите имя пользователя' : null,
    email: !EMAIL_RE.test(email.trim()) ? 'Укажите email, например name@company.ru' : null,
    password: !password ? 'Введите пароль' : null,
    password2: tab === 'register' && password2 !== password ? 'Пароли не совпадают' : null,
  };
  const valid = !Object.values(errors).some(Boolean);
  const submit = () => {
    setTried(true);
    if (valid) form.run();
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
          <h1 style={{ fontSize: 36 }}>Кредит для бизнеса онлайн</h1>
          <p>Заполните профиль компании один раз, подайте заявку — банк проверит данные в ЕГРЮЛ, ФНС и БКИ, скоринговая модель посчитает решение, и вы увидите результат сразу.</p>
        </div>
        <Px name="heart" size={98} color="var(--c-lime)" />
      </section>

      <div className="grid-2">
        <section className="card">
          <div className="seg" role="tablist" aria-label="Вход или регистрация">
            <button type="button" role="tab" aria-pressed={tab === 'login'} aria-selected={tab === 'login'} onClick={() => setTab('login')}>
              Вход
            </button>
            <button type="button" role="tab" aria-pressed={tab === 'register'} aria-selected={tab === 'register'} onClick={() => setTab('register')}>
              Регистрация
            </button>
          </div>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            {tab === 'register' && <TextField label="Имя пользователя" value={username} onChange={setUsername} autoComplete="username" error={tried ? errors.username : null} />}
            <TextField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" error={tried ? errors.email : null} />
            <TextField label="Пароль" type="password" value={password} onChange={setPassword} autoComplete={tab === 'login' ? 'current-password' : 'new-password'} error={tried ? errors.password : null} />
            {tab === 'register' && <TextField label="Повторите пароль" type="password" value={password2} onChange={setPassword2} autoComplete="new-password" error={tried ? errors.password2 : null} />}
            {form.error && <ErrorState error={form.error} />}
            <div className="btn-row">
              <Btn view="accent" type="submit" loading={form.pending}>
                {tab === 'login' ? 'Войти' : 'Зарегистрироваться'}
              </Btn>
              {tab === 'register' && <span className="xs muted">После регистрации заполните профиль компании</span>}
            </div>
          </form>
        </section>

        <section className="card">
          <div className="row-c between">
            <h2 className="h2">Демо-аккаунты</h2>
            <Chip kind="lime">Для показа</Chip>
          </div>
          <span className="small muted">При первом входе аккаунт регистрируется в бэкенде и получает синтетический профиль компании. Исход — то, что вернёт скоринговая модель.</span>
          <div className="stack-s">
            {DEMO_COMPANIES.map((d) => (
              <div key={d.key} className="row-c" style={{ gap: 14, padding: '12px 0', borderTop: '1px solid var(--c-line)', flexWrap: 'nowrap' }}>
                <span aria-hidden="true" style={{ width: 44, height: 44, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-black)', color: 'var(--c-lime)', fontWeight: 700 }}>
                  {d.key.toUpperCase()}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{d.title}</div>
                  <div className="small muted">{d.scenario}</div>
                </div>
                <Btn view="outlined" size={40} onClick={() => demo.run(d)} loading={busyKey === d.key} disabled={!!busyKey && busyKey !== d.key}>
                  Войти
                </Btn>
              </div>
            ))}
            <div className="row-c" style={{ gap: 14, padding: '12px 0', borderTop: '1px solid var(--c-line)', flexWrap: 'nowrap' }}>
              <span aria-hidden="true" style={{ width: 44, height: 44, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-red)', color: '#fff', fontWeight: 700 }}>
                Б
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>Банк · администратор</div>
                <div className="small muted">Все заявки и статистика · {DEMO_ADMIN.email}</div>
              </div>
              <Btn view="primary" size={40} onClick={() => demo.run('admin')} loading={busyKey === 'admin'} disabled={!!busyKey && busyKey !== 'admin'}>
                Войти
              </Btn>
            </div>
          </div>
          {demo.error && <ErrorState error={demo.error} />}
        </section>
      </div>
    </main>
  );
}
