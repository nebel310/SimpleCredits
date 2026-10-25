import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useSession } from './api';
import { BankLayout, ClientLayout } from './layout/Layouts';
import { Toasts } from './ui/kit';
import { Login } from './pages/Login';
import { Home } from './pages/client/Home';
import { Products } from './pages/client/Products';
import { Profile } from './pages/client/Profile';
import { Apply } from './pages/client/Apply';
import { ApplicationCard, ApplicationsList } from './pages/client/Applications';
import { Admin, AdminApplication } from './pages/bank/Admin';

function Start() {
  const user = useSession((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === 'admin' ? '/bank' : '/home'} replace />;
}

const C = (el: JSX.Element) => <ClientLayout>{el}</ClientLayout>;
const B = (el: JSX.Element) => <BankLayout>{el}</BankLayout>;

export function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Start />} />
        <Route path="/login" element={<Login />} />
        <Route path="/home" element={C(<Home />)} />
        <Route path="/products" element={C(<Products />)} />
        <Route path="/profile" element={C(<Profile />)} />
        <Route path="/apply" element={C(<Apply />)} />
        <Route path="/applications" element={C(<ApplicationsList />)} />
        <Route path="/applications/:id" element={C(<ApplicationCard />)} />
        <Route path="/bank" element={B(<Admin />)} />
        <Route path="/bank/applications/:id" element={B(<AdminApplication />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toasts />
    </HashRouter>
  );
}
