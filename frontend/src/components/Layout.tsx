import React, { useState, useEffect, useRef } from 'react';
import { LogOut, MessageSquare, FolderOpen, Shield, Users, BarChart2 } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import logoSmall from '../assets/ucdb-ia2-removebg-preview.png'; // Logo secundário

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
              console.log("Layout: Cleaning up WebSocket");
              wsRef.current.close();
              wsRef.current = null;
            }
          };
        }
      } catch (e) {
        console.error("Layout: Error parsing nexus_user:", e);
      }
    }

    return () => {
      mounted = false;
    };
  }, [userRole]);

  const connectWebSocket = (userId: string) => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // Força 127.0.0.1 se for localhost para evitar problemas de roteamento Docker/IPv6
    let hostname = window.location.hostname;
    if (hostname === 'localhost') hostname = '127.0.0.1';
    
    const host = `${hostname}:8000`;
    const wsUrl = `${protocol}//${host}/ws/${userId}`;
    console.log("Layout: Connecting to:", wsUrl);
    
    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("Layout: WebSocket connected");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'online_count') {
            setOnlineCount(data.count);
          }
        } catch (e) {
          console.error("Layout: WS message error:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("Layout: WebSocket error", error);
      };

      ws.onclose = (event) => {
        // Só tenta reconectar se não foi um fechamento proposital (cleanup)
        if (event.code !== 1000 && event.code !== 1001) {
          console.log("Layout: WebSocket closed abnormally", event.code);
          wsRef.current = null;
          if (localStorage.getItem('nexus_user')) {
            setTimeout(() => connectWebSocket(userId), 5000);
          }
        } else {
          console.log("Layout: WebSocket closed normally");
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error("Layout: Failed to create WebSocket:", err);
    }
  };

  // Função para definir a cor do ícone ativo baseada na rota
  const getBtnClass = (path: string, activeColor: string) => 
    `p-3 rounded-xl transition-all duration-200 ${
      location.pathname === path 
        ? `${activeColor} text-white shadow-lg` 
        : 'text-slate-500 hover:bg-slate-800'
    }`;

  return (
    <div className="flex h-screen bg-slate-950 text-white overflow-hidden">
      <nav className="w-20 flex flex-col items-center py-6 bg-slate-900 border-r border-slate-800 space-y-6">
        
        {/* Logo no topo da navegação */}
        <div className="mb-4 px-2">
          <img src={logoSmall} alt="UCDB" className="w-12 h-12 object-contain" />
        </div>

        {/* Botão Chat - Azul UCDB */}
        <button 
          onClick={() => navigate('/chat')} 
          className={getBtnClass('/chat', 'bg-[#003366]')}
          title="Chat"
        >
          <MessageSquare className="w-6 h-6" />
        </button>

        {/* Botão Dashboard DAC */}
        <button
          onClick={() => navigate('/dashboard')}
          className={getBtnClass('/dashboard', 'bg-emerald-700')}
          title="Dashboard Educação MS"
        >
          <BarChart2 className="w-6 h-6" />
        </button>

        {/* Botão Documentos */}
        {['professor', 'coordenador', 'administrador'].includes(userRole || '') && (
          <button 
            onClick={() => navigate('/documents')} 
            className={getBtnClass('/documents', 'bg-[#003366]')}
            title="Documentos"
          >
            <FolderOpen className="w-6 h-6" />
          </button>
        )}

        {/* Botão Admin - Grená UCDB */}
        {['administrador', 'coordenador'].includes(userRole || '') && (
          <button 
            onClick={() => navigate('/admin')} 
            className={getBtnClass('/admin', 'bg-[#990000]')}
            title="Administração"
          >
            <Shield className="w-6 h-6" />
          </button>
        )}
        
        <div className="mt-auto flex flex-col items-center gap-4">
          {/* Contador de Usuários Online - Visível apenas para Administradores */}
          {userRole === 'administrador' && (
            <div className="flex flex-col items-center gap-1 group" title={`${onlineCount} usuários únicos online`}>
              <div className="relative p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <Users className="w-5 h-5 text-blue-400" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-green-500 rounded-full animate-pulse border border-slate-900"></span>
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