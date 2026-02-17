import React, { useState, useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Login } from './components/Login';
import { ChatInterface } from './components/ChatInterface';
import { DocumentManager } from './components/DocumentManager';
import type { AuthState, User } from './types';

export default function App() {
  // 1. Inicializa lendo TUDo do LocalStorage (Token e Usuário)
  const [auth, setAuth] = useState<AuthState>(() => {
    const token = localStorage.getItem('nexus_token');
    const userStr = localStorage.getItem('nexus_user');
    return {
      isAuthenticated: !!token && !!userStr,
      user: userStr ? JSON.parse(userStr) : null,
      token: token
    };
  });

  // 2. Função de Login: Salva Token E Usuário
  const handleLogin = (token: string, user: User) => {
    localStorage.setItem('nexus_token', token);
    localStorage.setItem('nexus_user', JSON.stringify(user));
    setAuth({ isAuthenticated: true, user, token });
  };

  // 3. Função de Logout: Limpa tudo
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
        <Layout onLogout={handleLogout}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            
            {/* Rota Protegida do Chat */}
            <Route 
              path="/chat" 
              element={<ChatInterface user={auth.user} />} 
            />
            
            {/* Rota de Documentos */}
            <Route path="/documents" element={<DocumentManager />} />
          </Routes>
        </Layout>
      )}
    </HashRouter>
  );
}