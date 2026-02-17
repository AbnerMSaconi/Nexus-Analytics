import React, { useState } from 'react';
import { Lock, ShieldCheck, Server } from 'lucide-react';
// Importação correta do tipo para evitar erros do TypeScript
import type { User } from '../types';

interface LoginProps {
  onLogin: (token: string, user: User) => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // URL da API (ajuste se estiver rodando em outro IP/Porta)
  const API_URL = 'http://localhost:8000';

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // 1. Tenta autenticar (POST /login)
      // O backend espera "external_id" e "password"
      const loginResponse = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          external_id: username, 
          password: password 
        })
      });

      if (!loginResponse.ok) {
        if (loginResponse.status === 401) throw new Error('Usuário ou senha incorretos.');
        throw new Error('Erro ao conectar ao servidor.');
      }

      const loginData = await loginResponse.json();
      const token = loginData.access_token;

      // 2. Busca dados do usuário (GET /me) usando o token recebido
      const userResponse = await fetch(`${API_URL}/me`, {
        headers: { 
          'Authorization': `Bearer ${token}` 
        }
      });

      if (!userResponse.ok) throw new Error('Falha ao recuperar dados do usuário.');

      const userData = await userResponse.json();

      // 3. Monta o objeto final conforme a interface User
      // O backend retorna { id, username, role }, que bate com nossa interface
      const user: User = {
        id: userData.id, 
        username: userData.username,
        role: userData.role
      };

      // 4. Finaliza o login no Frontend
      onLogin(token, user);

    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Erro desconhecido ao tentar logar.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-800 border border-slate-700 rounded-xl shadow-2xl p-8 relative overflow-hidden">
        
        {/* Fundo decorativo */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-blue-400 to-blue-600 animate-pulse"></div>

        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4 border border-slate-600">
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
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              placeholder="Digite seu ID"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Senha</label>
            <div className="relative">
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
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
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center shadow-lg shadow-blue-900/20"
          >
            {loading ? (
              <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></span>
            ) : (
              'Entrar no Sistema'
            )}
          </button>
        </form>
        
        <div className="mt-8 text-center border-t border-slate-800 pt-4">
          <p className="text-xs text-slate-500">
            Conectado ao servidor seguro local.
          </p>
        </div>
      </div>
    </div>
  );
};