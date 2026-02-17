import React, { useState } from 'react';
import { Lock, ShieldCheck, Server } from 'lucide-react';
// Se você tiver o arquivo types, pode importar: import { User } from '../types';
// Caso contrário, definimos aqui para evitar erros:
interface User {
  id: string;
  username: string;
  role: string;
}

interface LoginProps {
  // ATENÇÃO: Mudamos a assinatura para aceitar token E usuário
  onLogin: (token: string, user: User) => void;
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

    setTimeout(() => {
      if (username === 'admin' && password === 'admin') {
        // CORREÇÃO CRÍTICA:
        // Agora enviamos o Token (1º arg) e o Objeto Usuário (2º arg)
        // Isso casa com o que o App.tsx espera receber.
        onLogin('fake-jwt-token-123456', {
          id: '1',
          username: username,
          role: 'admin'
        });
      } else {
        setError('Credenciais inválidas. Tente admin/admin.');
        setLoading(false);
      }
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-800 border border-slate-700 rounded-xl shadow-2xl p-8 relative overflow-hidden">
        
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-slate-900 rounded-full flex items-center justify-center mb-4 border border-slate-600">
            <Server className="w-8 h-8 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Nexus RAG System</h1>
          <p className="text-slate-400 text-sm mt-1">Acesso Seguro Corporativo</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Usuário</label>
            <input 
              type="text" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="admin"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Senha</label>
            <div className="relative">
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                placeholder="admin"
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
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center"
          >
            {loading ? 'Entrando...' : 'Entrar no Sistema'}
          </button>
        </form>
      </div>
    </div>
  );
};