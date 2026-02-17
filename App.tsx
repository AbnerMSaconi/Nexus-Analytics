import React, { useState, useEffect } from 'react';
import { HashRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
// Adicionei Shield para o ícone de admin
import { MessageSquare, Database, Settings, LogOut, Shield } from 'lucide-react';
import { Login } from './components/Login';
import { ChatInterface } from './components/ChatInterface';
import { DocumentManager } from './components/DocumentManager';
import { AdminPanel } from './components/AdminPanel'; // Importe o painel
import type { User, AuthState } from './types';

// --- LAYOUT PRINCIPAL (Mantendo seu design original) ---
const Layout: React.FC<{ children: React.ReactNode; user: User; onLogout: () => void }> = ({ children, user, onLogout }) => {
  return (
    <div className="flex h-screen w-screen bg-slate-950 overflow-hidden text-slate-200 font-sans">
      {/* Sidebar Original */}
      <nav className="w-20 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-6 gap-6 z-20">
        
        {/* Logo Original */}
        <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-900/40 mb-4">
          <span className="font-bold text-white text-lg">N</span>
        </div>

        {/* Link Chat */}
        <NavLink 
          to="/chat" 
          className={({ isActive }) => `p-3 rounded-xl transition-all ${isActive ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'}`}
          title="Chat"
        >
          <MessageSquare className="w-6 h-6" />
        </NavLink>

        {/* Link Documentos (Apenas para cargos permitidos) */}
        {['professor', 'coordenador', 'administrador'].includes(user.role) && (
          <NavLink 
            to="/documents" 
            className={({ isActive }) => `p-3 rounded-xl transition-all ${isActive ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'}`}
            title="Documentos"
          >
            <Database className="w-6 h-6" />
          </NavLink>
        )}

        {/* --- NOVO: Botão Admin (Apenas Administrador) --- */}
        {user.role === 'administrador' && (
          <NavLink 
            to="/admin" 
            className={({ isActive }) => `p-3 rounded-xl transition-all ${isActive ? 'bg-red-600 text-white shadow-lg shadow-red-900/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'}`}
            title="Administração"
          >
            <Shield className="w-6 h-6" />
          </NavLink>
        )}

        {/* Rodapé da Sidebar */}
        <div className="mt-auto flex flex-col gap-4">
           <button 
            className="p-3 text-slate-500 hover:bg-slate-800 hover:text-slate-300 rounded-xl transition-all"
            title="Configurações (Indisponível)"
          >
            <Settings className="w-6 h-6" />
          </button>
          
          <button 
            onClick={onLogout}
            className="p-3 text-red-400 hover:bg-red-900/20 rounded-xl transition-all"
            title="Sair"
          >
            <LogOut className="w-6 h-6" />
          </button>
        </div>
      </nav>

      {/* Área de Conteúdo */}
      <main className="flex-1 h-full w-full overflow-hidden relative bg-slate-950">
        {children}
      </main>
    </div>
  );
};

// --- APP PRINCIPAL ---
export default function App() {
  // 1. Inicializa lendo do LocalStorage (Persistência)
  const [auth, setAuth] = useState<AuthState>(() => {
    const token = localStorage.getItem('nexus_token');
    const userStr = localStorage.getItem('nexus_user');
    return {
      isAuthenticated: !!token && !!userStr,
      user: userStr ? JSON.parse(userStr) : null,
      token: token
    };
  });

  // 2. Login Real: Recebe token e objeto user completo do Login.tsx
  const handleLogin = (token: string, user: User) => {
    localStorage.setItem('nexus_token', token);
    localStorage.setItem('nexus_user', JSON.stringify(user));
    setAuth({ isAuthenticated: true, user, token });
  };

  // 3. Logout: Limpa tudo
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
        <Layout user={auth.user} onLogout={handleLogout}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            
            {/* Rota Chat */}
            <Route path="/chat" element={<ChatInterface user={auth.user} />} />
            
            {/* Rota Documentos */}
            <Route path="/documents" element={<DocumentManager />} />

            {/* --- NOVA ROTA DE ADMIN --- */}
            {auth.user.role === 'administrador' ? (
               <Route path="/admin" element={<AdminPanel />} />
            ) : (
               // Se tentar acessar sem ser admin, volta pro chat
               <Route path="/admin" element={<Navigate to="/chat" replace />} />
            )}
          </Routes>
        </Layout>
      )}
    </HashRouter>
  );
}