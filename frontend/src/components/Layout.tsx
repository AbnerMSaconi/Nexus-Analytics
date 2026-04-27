import React from 'react';
import { LogOut, MessageSquare, FolderOpen, Shield } from 'lucide-react';
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
        {userRole === 'administrador' && (
          <button 
            onClick={() => navigate('/admin')} 
            className={getBtnClass('/admin', 'bg-[#990000]')}
            title="Administração"
          >
            <Shield className="w-6 h-6" />
          </button>
        )}
        
        <div className="mt-auto">
          <button 
            onClick={onLogout} 
            className="p-3 text-red-500 hover:bg-red-950/20 rounded-xl transition-colors"
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