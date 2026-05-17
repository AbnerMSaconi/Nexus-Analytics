import React, { useState, useEffect, useRef } from 'react';
import { LogOut, Shield, Users, BarChart2 } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

interface LayoutProps {
  children: React.ReactNode;
  onLogout: () => void;
  userRole?: string;
}

export const Layout: React.FC<LayoutProps> = ({ children, onLogout, userRole }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [onlineCount, setOnlineCount] = useState(1);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let mounted = true;
    const userStr = localStorage.getItem('nexus_user');

    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        if (user?.id) {
          const timer = setTimeout(() => {
            if (mounted) connectWebSocket(user.id);
          }, 100);

          return () => {
            clearTimeout(timer);
            mounted = false;
            if (wsRef.current) {
              wsRef.current.close();
              wsRef.current = null;
            }
          };
        }
      } catch (e) {
        console.error('Layout: erro ao parsear nexus_user:', e);
      }
    }

    return () => { mounted = false; };
  }, [userRole]);

  const connectWebSocket = (userId: string) => {
    if (wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
       wsRef.current.readyState === WebSocket.CONNECTING)) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let hostname = window.location.hostname;
    if (hostname === 'localhost') hostname = '127.0.0.1';
    const ws = new WebSocket(`${protocol}//${hostname}:8000/ws/${userId}`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'online_count') setOnlineCount(data.count);
      } catch {}
    };

    ws.onclose = (event) => {
      if (event.code !== 1000 && event.code !== 1001) {
        wsRef.current = null;
        if (localStorage.getItem('nexus_user')) {
          setTimeout(() => connectWebSocket(userId), 5000);
        }
      }
    };

    wsRef.current = ws;
  };

  const getBtnClass = (path: string, activeColor: string) =>
    `p-3 rounded-xl transition-all duration-200 ${
      location.pathname === path
        ? `${activeColor} text-white shadow-lg`
        : 'text-slate-500 hover:bg-slate-800'
    }`;

  return (
    <div className="flex h-screen bg-slate-950 text-white overflow-hidden">
      <nav className="w-20 flex flex-col items-center py-6 bg-slate-900 border-r border-slate-800 space-y-4">

        {/* Logo Nexus — substitua pela imagem real quando disponível */}
        <div className="mb-2">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-900/40">
            <span className="text-white font-black text-xl">N</span>
          </div>
        </div>

        {/* Dashboard */}
        <button
          onClick={() => navigate('/dashboard')}
          className={getBtnClass('/dashboard', 'bg-blue-600')}
          title="Dashboard"
        >
          <BarChart2 className="w-6 h-6" />
        </button>

        {/* Admin — somente administrador */}
        {userRole === 'administrador' && (
          <button
            onClick={() => navigate('/admin')}
            className={getBtnClass('/admin', 'bg-slate-700')}
            title="Administração"
          >
            <Shield className="w-6 h-6" />
          </button>
        )}

        <div className="mt-auto flex flex-col items-center gap-4">
          {/* Contador online — somente admin */}
          {userRole === 'administrador' && (
            <div
              className="flex flex-col items-center gap-1"
              title={`${onlineCount} usuário(s) online`}
            >
              <div className="relative p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <Users className="w-5 h-5 text-blue-400" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-green-500 rounded-full animate-pulse border border-slate-900" />
              </div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                {onlineCount} ON
              </span>
            </div>
          )}

          <button
            onClick={onLogout}
            className="p-3 text-red-500 hover:bg-red-950/20 rounded-xl transition-colors"
            title="Sair"
          >
            <LogOut className="w-6 h-6" />
          </button>
        </div>
      </nav>

      <main className="flex-1 overflow-hidden relative bg-[#020617]">
        {children}
      </main>
    </div>
  );
};
