import React, { useState } from 'react';
import { HashRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { MessageSquare, Database, Settings, LogOut } from 'lucide-react';
import { Login } from './components/Login';
import { ChatInterface } from './components/ChatInterface';
import { DocumentManager } from './components/DocumentManager';
import type { User, AuthState } from './types';

// Main Layout Component
const Layout: React.FC<{ children: React.ReactNode; user: User; onLogout: () => void }> = ({ children, user, onLogout }) => {
  return (
    <div className="flex h-screen w-screen bg-background overflow-hidden text-slate-200 font-sans">
      {/* App Sidebar */}
      <nav className="w-20 flex-shrink-0 bg-slate-900 border-r border-slate-700 flex flex-col items-center py-6 gap-6 z-20">
        <div className="w-10 h-10 bg-gradient-to-br from-primary to-accent rounded-lg flex items-center justify-center shadow-lg shadow-blue-900/40 mb-4">
          <span className="font-bold text-white text-lg">N</span>
        </div>

        <NavLink 
          to="/chat" 
          className={({ isActive }) => `p-3 rounded-xl transition-all ${isActive ? 'bg-primary text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'}`}
          title="Chat"
        >
          <MessageSquare className="w-6 h-6" />
        </NavLink>

        <NavLink 
          to="/documents" 
          className={({ isActive }) => `p-3 rounded-xl transition-all ${isActive ? 'bg-primary text-white shadow-lg shadow-blue-900/20' : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'}`}
          title="Documentos"
        >
          <Database className="w-6 h-6" />
        </NavLink>

        <div className="mt-auto flex flex-col gap-4">
           <button 
            className="p-3 text-slate-500 hover:bg-slate-800 hover:text-slate-300 rounded-xl transition-all"
            title="Configurações (Demo)"
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

      {/* Main Content Area */}
      <main className="flex-1 h-full w-full overflow-hidden relative">
        {children}
      </main>
    </div>
  );
};

export default function App() {
  const [auth, setAuth] = useState<AuthState>({
    isAuthenticated: false,
    user: null,
    token: null
  });

  const handleLogin = (username: string) => {
    // Mock user object
    const user: User = {
      id: 'u1',
      username: username,
      role: username === 'admin' ? 'admin' : 'user',
      lastLogin: new Date()
    };
    setAuth({ isAuthenticated: true, user, token: 'mock-jwt-token' });
  };

  const handleLogout = () => {
    setAuth({ isAuthenticated: false, user: null, token: null });
  };

  return (
    <HashRouter>
      {!auth.isAuthenticated ? (
        <Login onLogin={handleLogin} />
      ) : (
        <Layout user={auth.user!} onLogout={handleLogout}>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatInterface user={auth.user!} />} />
            <Route path="/documents" element={<DocumentManager />} />
          </Routes>
        </Layout>
      )}
    </HashRouter>
  );
}