import React, { useState } from 'react';
import { Lock, ShieldCheck, Server, UserPlus, LogIn, User as UserIcon } from 'lucide-react';
import type { User } from '../types';

interface LoginProps {
  onLogin: (token: string, user: User) => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
  // Estado para alternar entre Login e Registro
  const [isRegistering, setIsRegistering] = useState(false);
  
  // Campos do formulário
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const API_URL = 'http://localhost:8000';

  // Função auxiliar para buscar dados do usuário e finalizar
  const fetchUserAndLogin = async (token: string) => {
    const userResponse = await fetch(`${API_URL}/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!userResponse.ok) throw new Error('Falha ao obter dados do usuário.');

    const userData = await userResponse.json();
    
    // Finaliza o processo no App.tsx
    onLogin(token, {
      id: userData.id,
      username: userData.username || userData.full_name, // Fallback
      role: userData.role
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (isRegistering) {
        // --- LÓGICA DE REGISTRO ---
        if (password !== confirmPassword) {
          throw new Error('As senhas não coincidem.');
        }

        const signupResponse = await fetch(`${API_URL}/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            external_id: username, // Usando username como ID único
            full_name: fullName,
            password: password,
            role: 'user' // Padrão para novos usuários
          })
        });

        if (!signupResponse.ok) {
          const errData = await signupResponse.json();
          throw new Error(errData.detail || 'Erro ao criar conta. Tente outro usuário.');
        }

        // Se registrou com sucesso, o backend já retorna o token!
        const data = await signupResponse.json();
        await fetchUserAndLogin(data.access_token);

      } else {
        // --- LÓGICA DE LOGIN ---
        const loginResponse = await fetch(`${API_URL}/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            external_id: username, 
            password: password 
          })
        });

        if (!loginResponse.ok) {
          throw new Error('Usuário ou senha incorretos.');
        }

        const data = await loginResponse.json();
        await fetchUserAndLogin(data.access_token);
      }

    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Erro de conexão com o servidor.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-800 border border-slate-700 rounded-xl shadow-2xl p-8 relative overflow-hidden transition-all duration-500">
        
        {/* Fundo decorativo */}
        <div className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-blue-400 to-blue-600 transition-all duration-1000 ${loading ? 'animate-pulse' : ''}`}></div>

        <div className="flex flex-col items-center mb-6">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4 border border-slate-600 shadow-lg">
            <Server className="w-8 h-8 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Nexus RAG System</h1>
          <p className="text-slate-400 text-sm mt-1">
            {isRegistering ? 'Crie sua conta corporativa' : 'Acesso Seguro Corporativo'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          
          {/* Campo Nome Completo (Apenas Registro) */}
          {isRegistering && (
            <div className="animate-in fade-in slide-in-from-top-4 duration-300">
              <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Nome Completo</label>
              <div className="relative">
                <input 
                  type="text" 
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  placeholder="Seu Nome"
                />
                <UserIcon className="absolute left-3 top-3.5 w-5 h-5 text-slate-600" />
              </div>
            </div>
          )}

          {/* Campo Usuário */}
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Usuário (ID)</label>
            <input 
              type="text" 
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              placeholder="ex: usuario.admin"
            />
          </div>

          {/* Campo Senha */}
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Senha</label>
            <div className="relative">
              <input 
                type="password" 
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                placeholder="••••••••"
              />
              <Lock className="absolute right-3 top-3.5 w-5 h-5 text-slate-600" />
            </div>
          </div>

          {/* Campo Confirmar Senha (Apenas Registro) */}
          {isRegistering && (
            <div className="animate-in fade-in slide-in-from-top-4 duration-300">
              <label className="block text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">Confirmar Senha</label>
              <div className="relative">
                <input 
                  type="password" 
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  placeholder="••••••••"
                />
                <Lock className="absolute right-3 top-3.5 w-5 h-5 text-slate-600" />
              </div>
            </div>
          )}

          {error && (
            <div className="text-red-400 text-xs bg-red-900/20 p-3 rounded border border-red-900/50 flex items-center animate-pulse">
              <ShieldCheck className="w-4 h-4 mr-2 shrink-0" />
              {error}
            </div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center shadow-lg shadow-blue-900/20 mt-2"
          >
            {loading ? (
              <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></span>
            ) : (
              isRegistering ? (
                <><UserPlus className="w-5 h-5 mr-2" /> Criar Conta</>
              ) : (
                <><LogIn className="w-5 h-5 mr-2" /> Entrar no Sistema</>
              )
            )}
          </button>
        </form>

        {/* Botão de Alternância */}
        <div className="mt-6 text-center pt-4 border-t border-slate-700/50">
          <p className="text-slate-400 text-sm mb-2">
            {isRegistering ? 'Já possui acesso?' : 'Não tem uma conta?'}
          </p>
          <button 
            onClick={() => {
              setIsRegistering(!isRegistering);
              setError('');
            }}
            className="text-blue-400 hover:text-blue-300 text-sm font-medium hover:underline transition-colors"
          >
            {isRegistering ? 'Voltar para Login' : 'Criar nova conta'}
          </button>
        </div>
      </div>
    </div>
  );
};