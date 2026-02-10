import React, { useState, useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Login } from './components/Login';
import { ChatInterface } from './components/ChatInterface';
import { DocumentManager } from './components/DocumentManager';
import { AuthState, User } from './types';

export default function App() {
  const [auth, setAuth] = useState<AuthState>({
    isAuthenticated: !!localStorage.getItem('nexus_token'),
    user: null,
    token: localStorage.getItem('nexus_token')
  });

  const handleLogin = (token: string, user: User) => {
    localStorage.setItem('nexus_token', token);
    setAuth({ isAuthenticated: true, user, token });
  };

  const handleLogout = () => {
    localStorage.removeItem('nexus_token');
    setAuth({ isAuthenticated: false, user: null, token: null });
  };

  return (
    <HashRouter>
      {!auth.isAuthenticated ? (
        <Login onLogin={handleLogin} />
      ) : (
        <Layout onLogout={handleLogout}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatInterface token={auth.token} />} />
            <Route path="/documents" element={<DocumentManager />} />
          </Routes>
        </Layout>
      )}
    </HashRouter>
  );
}