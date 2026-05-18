import React, { useState } from 'react';
import { Lock, LogIn, ShieldCheck, User as UserIcon } from 'lucide-react';
import type { User } from '../types';

interface LoginProps {
  onLogin: (token: string, user: User) => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const API_URL = `http://${window.location.hostname}:8000`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ external_id: username, password })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(
          typeof err.detail === 'string' ? err.detail : 'Credenciais inválidas.'
        );
      }

      const data = await res.json();

      const meRes = await fetch(`${API_URL}/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` }
      });

      if (!meRes.ok) throw new Error('Falha ao obter dados do usuário.');

      const me = await meRes.json();
      onLogin(data.access_token, {
        id: me.id,
        username: me.username || me.full_name,
        full_name: me.full_name,
        role: me.role,
        course: me.course
      });
    } catch (err: any) {
      setError(err.message || 'Erro de conexão com o servidor.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl shadow-2xl p-8 relative overflow-hidden">

        {/* Faixa decorativa */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-cyan-500 to-blue-600" />

        <div className="flex flex-col items-center mb-8">
          {/* Logo placeholder — substitua pelo arquivo real quando disponível */}
          <div className="mb-5 w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-900/40">
            <span className="text-white font-black text-3xl tracking-tighter">N</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Nexus</h1>
          <p className="text-slate-400 text-sm mt-1 uppercase tracking-widest font-medium">
            Plataforma de Análise de Dados
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">
              Usuário
            </label>
            <div className="relative">
              <input
                type="text"
                required
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition-all"
                placeholder="Login"
              />
              <UserIcon className="absolute left-3 top-3.5 w-5 h-5 text-slate-600" />
            </div>
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">
              Senha
            </label>
            <div className="relative">
              <input
                type="password"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 pl-4 pr-10 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition-all"
                placeholder="••••••••"
              />
              <Lock className="absolute right-3 top-3.5 w-5 h-5 text-slate-600" />
            </div>
          </div>

          {error && (
            <div className="text-red-400 text-xs bg-red-900/20 p-3 rounded border border-red-900/50 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-4 rounded-lg transition-all flex items-center justify-center shadow-lg shadow-blue-900/20 mt-6 active:scale-[0.98]"
          >
            {loading ? (
              <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
            ) : (
              <><LogIn className="w-5 h-5 mr-2" /> ENTRAR</>
            )}
          </button>
        </form>

        <p className="text-center text-slate-600 text-xs mt-8">
          Acesso restrito. Solicite credenciais ao administrador.
        </p>
      </div>
    </div>
  );
};
