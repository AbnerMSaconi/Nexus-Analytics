// frontend/src/components/DocumentManager.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Folder, FileText, Upload, Search, Database, RefreshCw, AlertCircle, ChevronRight, X, FileUp } from 'lucide-react'; 
import { StorageService } from '../services/storageService';
import type { Folder as FolderType } from '../types';
import { api } from '../assets/api';

export const DocumentManager: React.FC = () => {
  const [folders, setFolders] = useState<FolderType[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});
  
  // Estados do Modal de Upload
  const [showModal, setShowModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState({ type: '', msg: '' });
  
  // Estados do Formulário
  const [selectedArea, setSelectedArea] = useState('');
  const [newAreaName, setNewAreaName] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => { 
    loadData(); 
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const loadData = async () => {
    try {
      const data = await StorageService.getFolders();
      setFolders(data);
    } catch (error) { console.error("Erro ao carregar:", error); }
  };

  const user = (() => {
    try { return JSON.parse(localStorage.getItem('nexus_user') || 'null'); } catch { return null; }
  })();
  const canIngest = user && ['professor', 'coordenador', 'administrador', 'admin'].includes(user.role);

  // Conectar WebSocket para acompanhar progresso
  const connectWebSocket = (userId: string) => {
    if (wsRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/^https?:\/\//, '') : 'localhost:8000';
    const ws = new WebSocket(`${protocol}//${host}/ws/${userId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'processing_complete') {
        setUploadStatus({ type: 'success', msg: data.message });
        setUploading(false);
        loadData();
        
        // Fecha após 3 segundos após o sucesso real
        setTimeout(() => {
          setShowModal(false);
          setSelectedFiles([]);
          setSelectedArea('');
          setNewAreaName('');
          setUploadStatus({ type: '', msg: '' });
        }, 3000);
      } else if (data.type === 'processing_warning') {
        setUploadStatus({ type: 'info', msg: data.message });
      }
    };

    ws.onclose = () => { wsRef.current = null; };
    wsRef.current = ws;
  };

  const toggleFolder = (folderId: string) => {
    setExpandedFolders(prev => ({ ...prev, [folderId]: !prev[folderId] }));
  };

  // Funções de manipulação de Arquivos
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files);
      setSelectedFiles(prev => [...prev, ...filesArray]);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Disparo do Upload
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem('nexus_token');
    
    // Define a área alvo (existente ou nova)
    const finalArea = selectedArea === 'new' ? newAreaName : selectedArea;

    if (!finalArea.trim()) {
      setUploadStatus({ type: 'error', msg: 'Por favor, selecione ou digite o nome da área.' });
      return;
    }
    if (selectedFiles.length === 0) {
      setUploadStatus({ type: 'error', msg: 'Selecione ao menos um arquivo.' });
      return;
    }
    if (!token || !user) return;

    setUploading(true);
    setUploadStatus({ type: 'info', msg: 'Enviando arquivos para o servidor...' });

    try {
      // Abre conexão WS antes ou durante o upload para garantir que pegamos a volta
      connectWebSocket(user.id);
      
      await api.uploadDocumentsToArea(finalArea, selectedFiles, token);
      
      setUploadStatus({ 
        type: 'info', 
        msg: 'Arquivos enviados! O servidor está fatiando e indexando os vetores agora. Aguarde...' 
      });
      
      // O fechamento agora acontece no onmessage do WebSocket
      
    } catch (error: any) {
      setUploadStatus({ type: 'error', msg: `Erro: ${error.message}` });
      setUploading(false);
    }
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf': return 'text-red-400';
      case 'xlsx': return 'text-green-400';
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
    <div className="h-full flex flex-col p-6 overflow-hidden relative">
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
        
        {/* BOTÃO DE ABRIR MODAL */}
        {canIngest && (
          <button 
            onClick={() => setShowModal(true)}
            className="px-4 py-2 rounded-lg flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white transition-colors"
          >
            <Upload className="w-4 h-4"/> Enviar Documentos
          </button>
        )}
      </div>

      <div className="mb-6 relative">
        <Search className="absolute left-3 top-3 w-5 h-5 text-slate-500" />
        <input 
          type="text" 
          placeholder="Buscar nos documentos..." 
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-slate-900 border border-slate-700 text-white rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:border-blue-500 transition-colors"
        />
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-2 scrollbar-thin scrollbar-thumb-slate-800">
        {filteredFolders.length === 0 && (
          <div className="text-center py-10 text-slate-500">Nenhum documento encontrado.</div>
        )}

        {filteredFolders.map(folder => {
          const isExpanded = expandedFolders[folder.id] || searchTerm.trim().length > 0;

          return (
            <div key={folder.id} className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden transition-all duration-300">
              <div 
                onClick={() => toggleFolder(folder.id)}
                className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-slate-800/60 transition-colors select-none group"
              >
                <ChevronRight className={`w-4 h-4 text-slate-500 transition-transform duration-200 group-hover:text-slate-300 ${isExpanded ? 'rotate-90 text-slate-300' : ''}`} />
                <Folder className="w-5 h-5 text-yellow-500/80" />
                <h3 className="font-semibold text-slate-200">{folder.name}</h3>
                <span className="text-xs bg-slate-800/80 text-slate-400 px-2.5 py-1 rounded-full ml-auto border border-slate-700/50">
                  {folder.documents.length} arquivos
                </span>
              </div>
              
              {isExpanded && (
                <div className="divide-y divide-slate-800/50 bg-slate-950/30 border-t border-slate-800/50">
                  {folder.documents.map(doc => (
                    <div key={doc.id} className="p-4 hover:bg-slate-800/30 transition-colors cursor-default pl-12">
                      <div className="flex items-center gap-3">
                        <FileText className={`w-4 h-4 ${getFileIcon(doc.type)}`} />
                        <div>
                          <p className="text-sm font-medium text-slate-300">{doc.title}</p>
                          <p className="text-[11px] text-slate-500 mt-0.5">
  Indexado em: {(() => {
    const d = new Date(doc.uploadDate);
    return isNaN(d.getTime()) ? 'Recém-adicionado' : d.toLocaleDateString();
  })()}
</p>
                        </div>
                      </div>
                    </div>
                  ))}
                  {folder.documents.length === 0 && (
                    <div className="p-4 text-xs text-slate-500 pl-12 italic">Pasta vazia</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ========================================================== */}
      {/* MODAL DE UPLOAD DE ARQUIVOS INTERATIVO */}
      {/* ========================================================== */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            
            <div className="flex justify-between items-center p-6 border-b border-slate-800 bg-slate-800/40">
              <h2 className="text-lg font-bold flex items-center gap-2">
                <FileUp className="w-5 h-5 text-blue-500"/> Enviar para a Base de Dados
              </h2>
              <button onClick={() => !uploading && setShowModal(false)} className="text-slate-400 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="p-6 overflow-y-auto flex-1 flex flex-col gap-6">
              
              {/* Seleção de Área */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-300">Área de Conhecimento (Index)</label>
                <select 
                  value={selectedArea}
                  onChange={(e) => setSelectedArea(e.target.value)}
                  disabled={uploading}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 outline-none focus:border-blue-500 text-slate-200"
                >
                  <option value="" disabled>Selecione a área onde os arquivos serão salvos...</option>
                  {folders.map(f => (
                    <option key={f.id} value={f.name}>{f.name}</option>
                  ))}
                  <option value="new" className="font-bold text-blue-400">+ Criar Nova Área</option>
                </select>

                {selectedArea === 'new' && (
                  <div className="pt-2 animate-in fade-in slide-in-from-top-2">
                    <input 
                      type="text" 
                      placeholder="Nome da nova área (Ex: Biomedicina, Logística...)"
                      value={newAreaName}
                      onChange={(e) => setNewAreaName(e.target.value)}
                      disabled={uploading}
                      className="w-full bg-slate-950 border border-blue-500/50 rounded-lg px-4 py-3 outline-none focus:border-blue-500 text-slate-200"
                      autoFocus
                    />
                  </div>
                )}
              </div>

              {/* Upload de Arquivos via OS */}
              <div className="space-y-2 flex-1">
                <label className="text-sm font-medium text-slate-300">Arquivos (PDF, TXT, DOCX)</label>
                
                <input 
                  type="file" 
                  multiple 
                  accept=".pdf,.txt,.docx"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  className="hidden"
                  disabled={uploading}
                />
                
                <div 
                  onClick={() => !uploading && fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 transition-colors ${
                    uploading ? 'border-slate-800 bg-slate-900/50 cursor-not-allowed opacity-50' : 'border-slate-700 hover:border-blue-500 hover:bg-slate-800/30 cursor-pointer'
                  }`}
                >
                  <div className="bg-slate-800 p-3 rounded-full">
                    <Upload className="w-6 h-6 text-slate-400" />
                  </div>
                  <div className="text-center">
                    <p className="text-slate-300 font-medium">Clique para escolher os arquivos</p>
                    <p className="text-xs text-slate-500 mt-1">O explorador do sistema será aberto.</p>
                  </div>
                </div>

                {/* Lista de Arquivos Selecionados */}
                {selectedFiles.length > 0 && (
                  <div className="mt-4 space-y-2 max-h-40 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                    {selectedFiles.map((file, idx) => (
                      <div key={idx} className="flex items-center justify-between bg-slate-950 border border-slate-800 p-2 rounded-lg">
                        <div className="flex items-center gap-2 overflow-hidden">
                          <FileText className="w-4 h-4 text-blue-400 flex-shrink-0" />
                          <span className="text-xs text-slate-300 truncate">{file.name}</span>
                        </div>
                        <button 
                          type="button" 
                          onClick={() => removeFile(idx)}
                          disabled={uploading}
                          className="text-slate-500 hover:text-red-400 p-1"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Feedback de Status */}
              {uploadStatus.msg && (
                <div className={`p-4 rounded-lg flex items-center gap-3 text-sm border ${
                  uploadStatus.type === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 
                  uploadStatus.type === 'success' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 
                  'bg-blue-500/10 text-blue-400 border-blue-500/20'
                }`}>
                  {uploading ? <RefreshCw className="w-5 h-5 animate-spin flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
                  <p>{uploadStatus.msg}</p>
                </div>
              )}

              {/* Botões do Modal */}
              <div className="pt-2 flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={() => setShowModal(false)}
                  disabled={uploading}
                  className="px-5 py-2.5 text-slate-400 hover:text-white transition-colors"
                >
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  disabled={uploading || selectedFiles.length === 0 || !selectedArea}
                  className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {uploading ? 'Processando Vetores...' : 'Iniciar Indexação'}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}
    </div>
  );
};