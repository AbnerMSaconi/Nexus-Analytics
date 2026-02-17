import React from 'react';
import { LogOut, MessageSquare, FolderOpen, Shield } from 'lucide-react'; // Importe o Shield
import { useNavigate, useLocation } from 'react-router-dom';

interface LayoutProps {
  children: React.ReactNode;
  onLogout: () => void;
  userRole?: string; // Novo prop para saber se mostramos o botão
}

export const Layout: React.FC<LayoutProps> = ({ children, onLogout, userRole }) => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex h-screen bg-slate-950 text-white overflow-hidden">
      <nav className="w-16 flex flex-col items-center py-4 bg-slate-900 border-r border-slate-800 space-y-4">
        
        {/* Chat */}
        <button 
          onClick={() => navigate('/chat')}
          className={`p-3 rounded-xl transition-colors ${location.pathname === '/chat' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
          title="Chat"
        >
          <MessageSquare className="w-6 h-6" />
        </button>

        {/* Documentos (Apenas Prof/Coord/Admin) */}
        {['professor', 'coordenador', 'administrador'].includes(userRole || '') && (
          <button 
            onClick={() => navigate('/documents')}
            className={`p-3 rounded-xl transition-colors ${location.pathname === '/documents' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
            title="Documentos"
          >
            <FolderOpen className="w-6 h-6" />
          </button>
        )}

        {/* --- NOVO: Botão de Admin --- */}
        {userRole === 'administrador' && (
          <button 
            onClick={() => navigate('/admin')}
            className={`p-3 rounded-xl transition-colors ${location.pathname === '/admin' ? 'bg-red-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
            title="Administração"
          >
            <Shield className="w-6 h-6" />
          </button>
        )}
        
        <div className="mt-auto">
          <button onClick={onLogout} className="p-3 text-red-400 hover:bg-slate-800 rounded-xl transition-colors">
            <LogOut className="w-6 h-6" />
          </button>
        </div>
      </nav>

      <main className="flex-1 overflow-hidden relative">
        {children}
      </main>
    </div>
  );
};