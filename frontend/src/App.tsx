import { useState } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Login } from './components/Login';
import { AdminPanel } from './components/AdminPanel';
import { DashboardDAC } from './components/DashboardDAC';
import type { AuthState, User } from './types';

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
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardDAC />} />
            {auth.user.role === 'administrador' ? (
              <Route path="/admin" element={<AdminPanel />} />
            ) : (
              <Route path="/admin" element={<Navigate to="/dashboard" replace />} />
            )}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Layout>
      )}
    </HashRouter>
  );
}
