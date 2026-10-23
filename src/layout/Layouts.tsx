import { type ReactNode } from 'react';
import { Link, NavLink, Navigate, useNavigate } from 'react-router-dom';
import { isBankRole } from '../api';
import { useSession } from '../lib/hooks';
import { ROLE_NAME } from '../lib/status';
import { AiAssistant } from '../ai/AiAssistant';
import { COMPANY_SHORT } from '../lib/companies';

function LogoSlot() {
  // Место под официальный логотип банка: файл вставляет команда (организаторы разрешили)
  return (
    <span className="logo-slot" title="Место для официального логотипа">
      ЛОГО
    </span>
  );
}

export function ClientLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useSession();
  const nav = useNavigate();
  if (!user) return <Navigate to="/login" replace />;
  if (isBankRole(user.role)) return <Navigate to="/bank" replace />;
  return (
    <>
      <header className="hdr">
        <div className="wrap hdr-in">
          <Link to="/home" className="brand">
            <LogoSlot />
            <span>Кредитный кабинет</span>
          </Link>
          <nav className="nav" aria-label="Разделы кабинета">
            <NavLink to="/home">Главная</NavLink>
            <NavLink to="/applications">Заявки</NavLink>
            <NavLink to="/documents">Документы</NavLink>
          </nav>
          <div className="hdr-right">
            <span className="proto">Прототип · данные синтетические</span>
            <button
              type="button"
              className="who"
              onClick={() => {
                logout();
                nav('/login');
              }}
              title="Сменить тестовый аккаунт"
            >
              <b>{COMPANY_SHORT[user.companyId!]}</b>
              <span>
                {user.name} · {ROLE_NAME[user.role]} · сменить
              </span>
            </button>
          </div>
        </div>
      </header>
      <main className="wrap page-main" id="main">
        {children}
      </main>
      <AiAssistant />
    </>
  );
}

export function BankLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useSession();
  const nav = useNavigate();
  if (!user) return <Navigate to="/login" replace />;
  if (!isBankRole(user.role)) return <Navigate to="/home" replace />;
  return (
    <>
      <header className="hdr dark">
        <div className="wrap hdr-in">
          <Link to="/bank" className="brand">
            <LogoSlot />
            <span>Кабинет банка</span>
          </Link>
          <nav className="nav" aria-label="Разделы банка">
            <NavLink to="/bank" end>
              Очередь задач
            </NavLink>
            <NavLink to="/bank/all">Все заявки</NavLink>
          </nav>
          <div className="hdr-right">
            <span className="proto">Прототип</span>
            <button
              type="button"
              className="who"
              onClick={() => {
                logout();
                nav('/login');
              }}
              title="Сменить тестовый аккаунт"
            >
              <b>{user.name}</b>
              <span>
                {ROLE_NAME[user.role]}
                {user.authorityLimit ? ` · лимит ${user.authorityLimit / 1_000_000} млн ₽` : ''} · сменить
              </span>
            </button>
          </div>
        </div>
      </header>
      <main className="wrap page-main" id="main">
        {children}
      </main>
      <AiAssistant />
    </>
  );
}

export function DemoLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="hdr demo">
        <div className="wrap hdr-in">
          <Link to="/login" className="brand">
            <LogoSlot />
            <span>Демо для жюри</span>
          </Link>
          <nav className="nav" aria-label="Демо">
            <NavLink to="/demo/simulator">Пульт источников</NavLink>
            <NavLink to="/demo/mirror">Режим зеркала</NavLink>
          </nav>
          <div className="hdr-right">
            <Link to="/login" className="who" style={{ textDecoration: 'none' }}>
              <b>К входу</b>
              <span>выбрать роль</span>
            </Link>
          </div>
        </div>
      </header>
      <main className="wrap page-main" id="main">
        {children}
      </main>
    </>
  );
}
