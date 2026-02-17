import React from 'react';
import { LogOut, MessageSquare, FolderOpen } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

interface LayoutProps {
  children: React.ReactNode;
  onLogout: () => void;
}

export const Layout: React.FC<LayoutProps> = ({ children, onLogout }) => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex h-screen bg-slate-950 text-white overflow-hidden">
      {/* Sidebar */}
      <nav className="w-16 flex flex-col items-center py-4 bg-slate-900 border-r border-slate-800 space-y-4">
        <button 
          onClick={() => navigate('/chat')}
          className={`p-3 rounded-xl transition-colors ${location.pathname === '/chat' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        >
          <MessageSquare className="w-6 h-6" />
        </button>
        <button 
          onClick={() => navigate('/documents')}
          className={`p-3 rounded-xl transition-colors ${location.pathname === '/documents' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        >
          <FolderOpen className="w-6 h-6" />
        </button>
        
        <div className="mt-auto">
          <button 
            onClick={onLogout}
            className="p-3 text-red-400 hover:bg-slate-800 rounded-xl transition-colors"
          >
            <LogOut className="w-6 h-6" />
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden relative">
        {children}
      </main>
    </div>
  );
};