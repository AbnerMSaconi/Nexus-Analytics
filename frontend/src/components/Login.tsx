import React, { useState } from 'react';
import { Lock, ShieldCheck, Server } from 'lucide-react';

interface LoginProps {
  onLogin: (username: string) => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    // Simulate cryptographic verification
    setTimeout(() => {
      if (username === 'admin' && password === 'admin') {
        onLogin(username);
      } else {
        setError('Credenciais inválidas. Tente admin/admin.');
        setLoading(false);
      }
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface border border-slate-700 rounded-xl shadow-2xl p-8 relative overflow-hidden">
        
        {/* Decorative background element */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary via-accent to-primary animate-pulse"></div>

        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-slate-900 rounded-full flex items-center justify-center mb-4 border border-slate-600">
            <Server className="w-8 h-8 text-accent" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Nexus RAG System</h1>
          <p className="text-slate-400 text-sm mt-1">Acesso Seguro Corporativo</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Usuário</label>
            <div className="relative">
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all"
                placeholder="Identificação"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Senha</label>
            <div className="relative">
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all"
                placeholder="••••••••"
              />
              <Lock className="absolute right-3 top-3.5 w-5 h-5 text-slate-600" />
            </div>
          </div>

          {error && (
            <div className="text-red-400 text-sm bg-red-900/20 p-3 rounded border border-red-900/50 flex items-center">
              <ShieldCheck className="w-4 h-4 mr-2" />
              {error}
            </div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-primary hover:bg-blue-600 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center shadow-lg shadow-blue-900/20"
          >
            {loading ? (
              <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></span>
            ) : (
              'Entrar no Sistema'
            )}
          </button>
        </form>

        <div className="mt-8 text-center border-t border-slate-700 pt-4">
          <p className="text-xs text-slate-500">
            Sistema monitorado. Todas as ações são registradas.
            <br/> Versão 1.0.4-SafeGuard
          </p>
        </div>
      </div>
    </div>
  );
};