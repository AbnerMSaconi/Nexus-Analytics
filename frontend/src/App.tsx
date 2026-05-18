import { useState } from 'react';
import { HashRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Login } from './components/Login';
import { AdminPanel } from './components/AdminPanel';
import { DashboardDAC } from './components/DashboardDAC';
import type { AuthState, User } from './types';

function AppRoutes({ userRole }: { userRole: string }) {
  const location = useLocation();
  const isDashboard = location.pathname === '/dashboard' || location.pathname === '/';
  const isAdmin = location.pathname === '/admin';

  return (
    <>
      {/* DashboardDAC sempre montado — só escondido via CSS fora da rota */}
      <div className={isDashboard ? 'h-full overflow-hidden' : 'hidden'}>
        <DashboardDAC />
      </div>

      {userRole === 'administrador' && isAdmin && <AdminPanel />}

      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={null} />
        <Route path="/admin" element={
          userRole === 'administrador' ? null : <Navigate to="/dashboard" replace />
        } />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  const [auth, setAuth] = useState<AuthState>(() => {
    const token = localStorage.getItem('nexus_token');
    const userStr = localStorage.getItem('nexus_user');
    return {
      isAuthenticated: !!token && !!userStr,
      user: userStr ? JSON.parse(userStr) : null,
      token: token
    };
  });

  const handleLogin = (token: string, user: User) => {
    localStorage.setItem('nexus_token', token);
    localStorage.setItem('nexus_user', JSON.stringify(user));
    setAuth({ isAuthenticated: true, user, token });
  };

  const handleLogout = () => {
    localStorage.removeItem('nexus_token');
    localStorage.removeItem('nexus_user');
    setAuth({ isAuthenticated: false, user: null, token: null });
  };

  return (
    <HashRouter>
      {!auth.isAuthenticated || !auth.user ? (
        <Login onLogin={handleLogin} />
      ) : (
        <Layout onLogout={handleLogout} userRole={auth.user.role}>
          <AppRoutes userRole={auth.user.role} />
        </Layout>
      )}
    </HashRouter>
  );
}
