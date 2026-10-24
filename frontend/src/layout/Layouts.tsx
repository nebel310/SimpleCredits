import { type ReactNode } from 'react';
import { Link, NavLink, Navigate, useNavigate } from 'react-router-dom';
import { useSession } from '../api';
import { signOut } from '../lib/auth';

function LogoSlot() {
  // Место под официальный логотип банка: файл вставляет команда (организаторы разрешили)
  return (
    <span className="logo-slot" title="Место для официального логотипа">
      ЛОГО
    </span>
  );
}

function Who({ title, sub }: { title: string; sub: string }) {
  const nav = useNavigate();
  return (
    <button
      type="button"
      className="who"
      onClick={async () => {
        await signOut();
        nav('/login');
      }}
      title="Выйти из аккаунта"
    >
      <b>{title}</b>
      <span>{sub} · выйти</span>
    </button>
  );
}

/** Кабинет предпринимателя (роль user) */
export function ClientLayout({ children }: { children: ReactNode }) {
  const user = useSession((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'admin') return <Navigate to="/bank" replace />;
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
            <NavLink to="/products">Продукты</NavLink>
            <NavLink to="/applications">Заявки</NavLink>
            <NavLink to="/profile">Профиль компании</NavLink>
          </nav>
          <div className="hdr-right">
            <span className="proto" title="Данные синтетические">Прототип</span>
            <Who title={user.company?.legal_name ?? user.username} sub="Предприниматель" />
          </div>
        </div>
      </header>
      <main className="wrap page-main" id="main">
        {children}
      </main>
    </>
  );
}

/** Кабинет банка (роль admin): все заявки и статистика */
export function BankLayout({ children }: { children: ReactNode }) {
  const user = useSession((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'admin') return <Navigate to="/home" replace />;
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
              Заявки и статистика
            </NavLink>
          </nav>
          <div className="hdr-right">
            <span className="proto">Прототип</span>
            <Who title={user.username} sub="Администратор" />
          </div>
        </div>
      </header>
      <main className="wrap page-main" id="main">
        {children}
      </main>
    </>
  );
}
