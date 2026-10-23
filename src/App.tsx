import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { isBankRole } from './api';
import { useSession } from './lib/hooks';
import { ClientLayout } from './layout/Layouts';
import { Toasts } from './ui/kit';
import { Login } from './pages/Login';
import { Dashboard } from './pages/client/Dashboard';
import { Wizard } from './pages/client/Wizard';
import { ApplicationCard, ApplicationsList } from './pages/client/Applications';
import { DocsRequest } from './pages/client/DocsRequest';
import { Decision } from './pages/client/Decision';
import { Signing } from './pages/client/Signing';

function Home() {
  const user = useSession((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={isBankRole(user.role) ? '/bank' : '/home'} replace />;
}

const C = (el: JSX.Element) => <ClientLayout>{el}</ClientLayout>;

export function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/home" element={C(<Dashboard />)} />
        <Route path="/apply" element={<Navigate to="/apply/goal" replace />} />
        <Route path="/apply/:step" element={C(<Wizard />)} />
        <Route path="/applications" element={C(<ApplicationsList />)} />
        <Route path="/applications/:id" element={C(<ApplicationCard />)} />
        <Route path="/applications/:id/documents" element={C(<DocsRequest />)} />
        <Route path="/applications/:id/decision" element={C(<Decision />)} />
        <Route path="/applications/:id/sign" element={C(<Signing />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toasts />
    </HashRouter>
  );
}
