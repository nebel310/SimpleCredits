import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { isBankRole } from './api';
import { useSession } from './lib/hooks';
import { Toasts } from './ui/kit';
import { Login } from './pages/Login';

function Home() {
  const user = useSession((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={isBankRole(user.role) ? '/bank' : '/home'} replace />;
}

export function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toasts />
    </HashRouter>
  );
}
