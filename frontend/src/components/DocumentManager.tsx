import React, { useState, useEffect } from 'react';
import { Folder, FileText, Upload, Search, Database, RefreshCw, AlertCircle } from 'lucide-react'; // Adicionados ícones
import { StorageService } from '../services/storageService';
import type { Folder as FolderType } from '../types';
import { api } from '../assets/api'; // Importação da API atualizada

export const DocumentManager: React.FC = () => {
  const [folders, setFolders] = useState<FolderType[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Novos estados para feedback visual
  const [ingesting, setIngesting] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const data = await StorageService.getFolders();
      setFolders(data);
    } catch (error) {
      console.error("Erro ao carregar:", error);
    }
  };

  // --- LÓGICA DE PERMISSÃO ---
  const getUserData = () => {
    try {
      const userStr = localStorage.getItem('nexus_user');
      return userStr ? JSON.parse(userStr) : null;
    } catch { return null; }
  };

  const user = getUserData();
  const canIngest = user && ['professor', 'coordenador', 'administrador', 'admin'].includes(user.role);

  // --- AÇÃO DE INGESTÃO ---
  const handleIngest = async () => {
    const token = localStorage.getItem('nexus_token');
    if (!canIngest || !token) {
        setStatusMsg("Erro: Sem permissão ou sessão inválida.");
        return;
    }

    setIngesting(true);
    setStatusMsg('Processando documentos no servidor...');

    try {
      // Chama o método específico criado no api.ts
      await api.ingestDocuments(token);
      
      setStatusMsg('Sucesso! Base atualizada.');
      await loadData(); // Recarrega a lista para mostrar novos arquivos
      
      setTimeout(() => setStatusMsg(''), 4000);
    } catch (error: any) {
      console.error(error);
      setStatusMsg(`Erro: ${error.message}`);
    } finally {
      setIngesting(false);
    }
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf': return 'text-red-400';
      case 'xlsx': return 'text-green-400';
      case 'docx': return 'text-blue-400';
      default: return 'text-slate-400';
    }
  };

  const filteredFolders = folders.map(folder => ({
    ...folder,
    documents: folder.documents.filter(doc => 
      doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doc.content.toLowerCase().includes(searchTerm.toLowerCase())
    )
  })).filter(f => f.documents.length > 0 || searchTerm === '');

  return (
    <div className="h-full flex flex-col p-6 overflow-hidden">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Database className="w-6 h-6 text-accent" />
            Base de Conhecimento
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            Gerenciamento de documentos vetorizados por setor.
          </p>
        </div>
        
        {/* Renderização Condicional do Botão */}
        {canIngest && (
          <div className="flex flex-col items-end gap-2">
            <button 
              onClick={handleIngest}
              disabled={ingesting}
              className={`
                px-4 py-2 rounded-lg flex items-center gap-2 transition-colors border 
                ${ingesting 
                  ? 'bg-slate-800 text-slate-500 border-slate-700 cursor-not-allowed' 
                  : 'bg-slate-700 hover:bg-slate-600 text-white border-slate-600'}
              `}
            >
              {ingesting ? <RefreshCw className="w-4 h-4 animate-spin"/> : <Upload className="w-4 h-4"/>}
              {ingesting ? 'Ingerindo...' : 'Ingerir Novos Arquivos'}
            </button>
            
            {statusMsg && (
              <span className={`text-xs flex items-center gap-1 ${statusMsg.includes('Erro') ? 'text-red-400' : 'text-green-400'}`}>
                {statusMsg.includes('Erro') && <AlertCircle className="w-3 h-3"/>}
                {statusMsg}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="mb-6 relative">
        <Search className="absolute left-3 top-3 w-5 h-5 text-slate-500" />
        <input 
          type="text" 
          placeholder="Buscar nos documentos..." 
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:border-accent"
        />
      </div>

      <div className="flex-1 overflow-y-auto space-y-6 pr-2">
        {filteredFolders.length === 0 && (
          <div className="text-center py-10 text-slate-500">
            Nenhum documento encontrado.
          </div>
        )}

        {filteredFolders.map(folder => (
          <div key={folder.id} className="bg-surface rounded-xl border border-slate-700 overflow-hidden">
            <div className="bg-slate-900/50 px-4 py-3 border-b border-slate-700 flex items-center gap-2">
              <Folder className="w-5 h-5 text-yellow-500" />
              <h3 className="font-semibold text-slate-200">{folder.name}</h3>
              <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full ml-auto">
                {folder.documents.length} arquivos
              </span>
            </div>
            
            <div className="divide-y divide-slate-700/50">
              {folder.documents.map(doc => (
                <div key={doc.id} className="p-4 hover:bg-slate-700/30 transition-colors group cursor-default">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <FileText className={`w-5 h-5 ${getFileIcon(doc.type)}`} />
                      <div>
                        <p className="text-sm font-medium text-slate-300 group-hover:text-white transition-colors">
                          {doc.title}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Indexado em: {new Date(doc.uploadDate).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                       <span className="text-[10px] uppercase border border-slate-600 text-slate-400 px-1.5 rounded">
                         Vetorizado
                       </span>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-slate-500 pl-8 line-clamp-1 italic">
                    Preview: "{doc.content.substring(0, 80)}..."
                  </div>
                </div>
              ))}
              {folder.documents.length === 0 && (
                <div className="p-4 text-xs text-slate-500 text-center italic">
                  Pasta vazia
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};