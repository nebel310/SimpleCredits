import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { isBankRole } from './api';
import { useSession } from './lib/hooks';
import { BankLayout, ClientLayout } from './layout/Layouts';
import { Toasts } from './ui/kit';
import { Login } from './pages/Login';
import { Dashboard } from './pages/client/Dashboard';
import { Wizard } from './pages/client/Wizard';
import { ApplicationCard, ApplicationsList } from './pages/client/Applications';
import { DocsRequest } from './pages/client/DocsRequest';
import { Decision } from './pages/client/Decision';
import { Signing } from './pages/client/Signing';
import { Loan } from './pages/client/Loan';
import { Documents } from './pages/client/Documents';
import { AllApplications, Queue } from './pages/bank/Queue';
import { BankApplication } from './pages/bank/BankApplication';
import { UwDecision } from './pages/bank/UwDecision';

function Home() {
  const user = useSession((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={isBankRole(user.role) ? '/bank' : '/home'} replace />;
}

const C = (el: JSX.Element) => <ClientLayout>{el}</ClientLayout>;
const B = (el: JSX.Element) => <BankLayout>{el}</BankLayout>;

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
        <Route path="/applications/:id/loan" element={C(<Loan />)} />
        <Route path="/documents" element={C(<Documents />)} />
        <Route path="/bank" element={B(<Queue />)} />
        <Route path="/bank/all" element={B(<AllApplications />)} />
        <Route path="/bank/applications/:id" element={B(<BankApplication />)} />
        <Route path="/bank/applications/:id/decision" element={B(<UwDecision />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toasts />
    </HashRouter>
  );
}
