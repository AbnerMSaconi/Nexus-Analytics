import React, { useState } from 'react';
import { Lock, ShieldCheck, UserPlus, LogIn, User as UserIcon, BookOpen } from 'lucide-react';
import type { User } from '../types';
import logoUcdb from '../assets/ucdb-ia-removebg-preview.png';

interface LoginProps {
  onLogin: (token: string, user: User) => void;
}

export const Login: React.FC<LoginProps> = ({ onLogin }) => {
  // Mantendo todos os estados originais
  const [isRegistering, setIsRegistering] = useState(false);
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [course, setCourse] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const API_URL = 'http://127.0.0.1:8000';

  // Lógica de busca de usuário mantida
  const fetchUserAndLogin = async (token: string) => {
    const userResponse = await fetch(`${API_URL}/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!userResponse.ok) throw new Error('Falha ao obter dados do usuário.');

    const userData = await userResponse.json();
    
    onLogin(token, {
      id: userData.id,
      username: userData.username || userData.full_name, 
      full_name: userData.full_name,
      role: userData.role,
      course: userData.course 
    });
  };

  // Lógica de submit mantida integralmente
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (isRegistering) {
        if (password !== confirmPassword) {
          throw new Error('As senhas não coincidem.');
        }

        const signupResponse = await fetch(`${API_URL}/signup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            external_id: username, 
            full_name: fullName,
            password: password,
            course: course,
            role: 'aluno'
          })
        });

        if (!signupResponse.ok) {
          const errData = await signupResponse.json();
          const errorMsg = typeof errData.detail === 'string' 
            ? errData.detail 
            : (Array.isArray(errData.detail) ? JSON.stringify(errData.detail[0].msg) : 'Erro ao criar conta.');
          throw new Error(errorMsg);
        }

        const data = await signupResponse.json();
        try {
            await fetchUserAndLogin(data.access_token);
        } catch (fetchErr) {
            onLogin(data.access_token, {
                id: username,
                username: fullName,
                role: 'aluno',
                course: course
            });
        }

      } else {
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
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl shadow-2xl p-8 relative overflow-hidden transition-all duration-500">
        
        {/* Faixa decorativa com as cores da UCDB (Azul e Grená) */}
        <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-[#003366] via-[#990000] to-[#003366]"></div>

        <div className="flex flex-col items-center mb-8">
          {/* Logo Centralizado */}
          <div className="mb-4 drop-shadow-lg">
            <img src={logoUcdb} alt="UCDB IA Logo" className="h-24 w-auto object-contain" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">UCDB-IA</h1>
          <p className="text-slate-400 text-sm mt-1 uppercase tracking-widest font-medium">
            {isRegistering ? 'Cadastro de Aluno' : 'Acesso Acadêmico'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          
          {isRegistering && (
            <div className="space-y-4 animate-in fade-in slide-in-from-top-4 duration-300">
              {/* Nome Completo */}
              <div>
                <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">Nome Completo</label>
                <div className="relative">
                  <input 
                    type="text" 
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:border-[#003366] focus:ring-1 focus:ring-[#003366] transition-all"
                    placeholder="Nome completo"
                  />
                  <UserIcon className="absolute left-3 top-3.5 w-5 h-5 text-slate-600" />
                </div>
              </div>

              {/* Curso */}
              <div>
                <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">Curso</label>
                <div className="relative">
                  <input 
                    type="text" 
                    required
                    value={course}
                    onChange={(e) => setCourse(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:border-[#003366] focus:ring-1 focus:ring-[#003366] transition-all"
                    placeholder="Engenharia de Computação..."
                  />
                  <BookOpen className="absolute left-3 top-3.5 w-5 h-5 text-slate-600" />
                </div>
              </div>
            </div>
          )}

          {/* Usuário */}
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">Usuário (ID/RA)</label>
            <input 
              type="text" 
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-[#003366] focus:ring-1 focus:ring-[#003366] transition-all"
              placeholder="ex: ra123456"
            />
          </div>

          {/* Senha */}
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">Senha</label>
            <div className="relative">
              <input 
                type="password" 
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-[#003366] focus:ring-1 focus:ring-[#003366] transition-all"
                placeholder="••••••••"
              />
              <Lock className="absolute right-3 top-3.5 w-5 h-5 text-slate-600" />
            </div>
          </div>

          {isRegistering && (
            <div className="animate-in fade-in slide-in-from-top-4 duration-300">
              <label className="block text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 ml-1">Confirmar Senha</label>
              <input 
                type="password" 
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 text-white rounded-lg py-3 px-4 focus:outline-none focus:border-[#003366] focus:ring-1 focus:ring-[#003366] transition-all"
                placeholder="••••••••"
              />
            </div>
          )}

          {error && (
            <div className="text-red-400 text-xs bg-red-900/20 p-3 rounded border border-red-900/50 flex items-center animate-in fade-in duration-300">
              <ShieldCheck className="w-4 h-4 mr-2 shrink-0" />
              {error}
            </div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-[#003366] hover:bg-[#004080] text-white font-bold py-4 rounded-lg transition-all flex items-center justify-center shadow-lg shadow-blue-900/10 mt-6 active:scale-[0.98]"
          >
            {loading ? (
              <span className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></span>
            ) : (
              isRegistering ? (
                <><UserPlus className="w-5 h-5 mr-2" /> CRIAR CONTA</>
              ) : (
                <><LogIn className="w-5 h-5 mr-2" /> ACESSAR SISTEMA</>
              )
            )}
          </button>
        </form>

        <div className="mt-8 text-center pt-6 border-t border-slate-800/50">
          <p className="text-slate-500 text-sm mb-2">
            {isRegistering ? 'Já possui acesso?' : 'Ainda não tem uma conta?'}
          </p>
          <button 
            onClick={() => {
              setIsRegistering(!isRegistering);
              setError('');
            }}
            className="text-blue-400 hover:text-blue-300 text-sm font-bold transition-colors underline-offset-4 hover:underline"
          >
            {isRegistering ? 'VOLTAR PARA LOGIN' : 'SOLICITAR NOVO ACESSO'}
          </button>
        </div>
      </div>
    </div>
  );
};