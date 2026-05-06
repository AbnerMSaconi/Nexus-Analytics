import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User as UserIcon, BookOpen, Clock, Plus, Cpu, Trash2, ExternalLink, Download } from 'lucide-react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { generateRAGResponse } from "../services/apiService";
import { StorageService } from '../services/storageService';
import { api } from '../assets/api';
import type { Message, ChatSession, User } from '../types';

declare global {
  interface Window {
    MathJax: any;
  }
}

interface ChatInterfaceProps {
  user: User;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ user }) => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [availableAreas, setAvailableAreas] = useState<string[]>(['Geral']);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null); 

  useEffect(() => {
    loadSessions();
    loadAreas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  const loadAreas = async () => {
    try {
      const response = await api.getKnowledgeAreas();
      // Áreas vindas das pastas no servidor (ex: index_engenharia -> Engenharia)
      const areasFromApi = response && response.data ? response.data.map((a: any) => a.area) : [];
      
      // Cursos do perfil do usuário
      const userCourses = user.course ? user.course.split(/[,;]/).map(c => c.trim()) : [];
      
      // Criamos um Set de nomes normalizados (lowercase) para evitar duplicatas visuais
      // mas mantemos a capitalização original para exibição
      const seen = new Set<string>();
      const uniqueList: string[] = [];
      
      // Ordem de prioridade: Geral -> Cursos do Usuário -> Outras Áreas da API
      const candidates = ['Geral', ...userCourses, ...areasFromApi];
      
      candidates.forEach(area => {
        if (!area) return;
        const normalized = area.toLowerCase().trim();
        if (!seen.has(normalized)) {
          seen.add(normalized);
          uniqueList.push(area);
        }
      });
      
      setAvailableAreas(uniqueList);
    } catch (e) {
      console.error("Erro ao carregar áreas:", e);
      const userCourses = user.course ? user.course.split(/[,;]/).map(c => c.trim()) : [];
      const fallback = Array.from(new Set(['Geral', ...userCourses]));
      setAvailableAreas(fallback);
    }
  };

  useEffect(() => {
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise().catch((err: any) => console.log('MathJax error:', err));
    }
  }, [sessions, isProcessing]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const loadSessions = async () => {
    const loadedSessions = await StorageService.getSessions(user.id);
    setSessions(loadedSessions);
    
    if (loadedSessions.length > 0) {
      if (!currentSessionId) setCurrentSessionId(loadedSessions[0].id);
    } else {
      createNewSession();
    }
  };

  const createNewSession = async () => {
    setSessions(prev => {
      if (prev.length > 0 && prev[0].messages.length === 0) {
        setCurrentSessionId(prev[0].id);
        return prev;
      }

      // Define a área inicial baseada no curso do usuário ou 'Geral'
      const initialArea = user.course ? user.course.split(/[,;]/)[0].trim() : 'Geral';

      const newSession: ChatSession = {
        id: crypto.randomUUID(),
        userId: user.id,
        title: 'Nova Conversa',
        messages: [],
        area: initialArea,
        createdAt: new Date(),
        updatedAt: new Date()
      };

      StorageService.saveSession(newSession);
      setCurrentSessionId(newSession.id);
      return [newSession, ...prev];
    });
  };

  const updateSessionArea = async (area: string) => {
    if (!currentSessionId) return;
    
    setSessions(prev => prev.map(s => {
      if (s.id === currentSessionId) {
        const updated = { ...s, area, updatedAt: new Date() };
        StorageService.saveSession(updated);
        return updated;
      }
      return s;
    }));
  };

  const deleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (window.confirm('Tem certeza que deseja excluir esta conversa?')) {
      await StorageService.deleteSession(sessionId, user.id);
      const updatedSessions = sessions.filter(s => s.id !== sessionId);
      setSessions(updatedSessions);
      if (sessionId === currentSessionId) {
        if (updatedSessions.length > 0) {
          setCurrentSessionId(updatedSessions[0].id);
        } else {
          createNewSession();
        }
      }
    }
  };

  const currentSession = sessions.find(s => s.id === currentSessionId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentSession?.messages, isProcessing]);

  const renderMarkdown = (content: string) => {
    try {
      const mathBlocks: string[] = [];
      const tempContent = content.replace(/(\$\$.*?\$\$|\$.*?\$)/gs, (match) => {
        mathBlocks.push(match);
        return `@@MATHBLOCK${mathBlocks.length - 1}@@`;
      });

      const html = marked.parse(tempContent, { async: false }) as string;
      const cleanHtml = DOMPurify.sanitize(html);
      const finalHtml = cleanHtml.replace(/@@MATHBLOCK(\d+)@@/g, (_, id) => {
        return mathBlocks[parseInt(id)];
      });

      return { __html: finalHtml };
    } catch (e) {
      return { __html: content };
    }
  };

  useEffect(() => {
    if (window.MathJax && window.MathJax.typesetPromise) {
      requestAnimationFrame(() => {
        window.MathJax.typesetPromise().catch((err: any) => console.error('MathJax error:', err));
      });
    }
  }, [sessions, isProcessing, currentSessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isProcessing) {
        handleSendMessage(e as unknown as React.FormEvent);
      }
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId) return;
    
    const userText = input;
    const sessionToUpdate = sessions.find(s => s.id === currentSessionId);
    if (!sessionToUpdate) return;

    setInput('');
    setIsProcessing(true);

    if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      timestamp: new Date()
    };

    const updatedSession = { 
      ...sessionToUpdate, 
      messages: [...sessionToUpdate.messages, userMsg],
      updatedAt: new Date()
    };
    
    if (updatedSession.messages.length === 1) {
      updatedSession.title = userText.substring(0, 30) + (userText.length > 30 ? '...' : '');
    }

    setSessions(prev => prev.map(s => s.id === currentSessionId ? updatedSession : s));
    await StorageService.saveSession(updatedSession);

    try {
      const token = localStorage.getItem('nexus_token');
      const areaSolicitada = sessionToUpdate.area || "Geral";
      const aiResponse = await generateRAGResponse(userText, areaSolicitada, token);

      const botMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: aiResponse.text,
        citations: aiResponse.citations,
        timestamp: new Date()
      };

      const finalSession = {
        ...updatedSession,
        messages: [...updatedSession.messages, botMsg],
        updatedAt: new Date()
      };

      setSessions(prev => prev.map(s => s.id === currentSessionId ? finalSession : s));
      await StorageService.saveSession(finalSession);

    } catch (error: any) {
      console.error("Erro no RAG:", error);
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `⚠️ **Erro de Conexão:** ${error.message || "Não foi possível conectar ao cérebro local."}`,
        timestamp: new Date()
      };
      setSessions(prev => prev.map(s => s.id === currentSessionId ? {
        ...s, messages: [...s.messages, errorMsg]
      } : s));
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar History */}
      <div className="w-64 bg-slate-900 border-r border-slate-700 flex flex-col hidden md:flex">
        <div className="p-4">
          <button 
            onClick={createNewSession}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 flex items-center justify-center gap-2 transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" /> Nova Conversa
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {sessions.map(session => (
            <div
              key={session.id}
              onClick={() => setCurrentSessionId(session.id)}
              className={`group relative w-full text-left p-3 rounded-lg cursor-pointer flex items-center justify-between transition-colors ${
                currentSessionId === session.id 
                  ? 'bg-slate-800 text-white border border-slate-700' 
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
              }`}
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <Clock className="w-4 h-4 min-w-[16px]" />
                <span className="truncate text-sm">{session.title}</span>
              </div>
              
              <button
                onClick={(e) => deleteSession(e, session.id)}
                className={`p-1.5 rounded-md hover:bg-red-500/20 hover:text-red-400 transition-all ${
                  currentSessionId === session.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                }`}
                title="Excluir conversa"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-slate-950 relative">
        {!currentSessionId ? (
          <div className="flex-1 flex items-center justify-center text-slate-500">
            Selecione ou inicie uma conversa.
          </div>
        ) : (
          <>
            {/* Header com Seletor de Área */}
            <div className="h-16 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50 backdrop-blur z-20">
              <div className="flex items-center gap-4">
                <div className="relative group">
                  <select
                    value={currentSession?.area || 'Geral'}
                    onChange={(e) => updateSessionArea(e.target.value)}
                    className="appearance-none bg-slate-800 border border-slate-700 text-white text-sm rounded-xl px-4 py-2 pr-10 focus:outline-none focus:border-blue-500 transition-all cursor-pointer hover:bg-slate-750 font-medium capitalize"
                  >
                    {availableAreas.map(area => (
                      <option key={area} value={area}>{area}</option>
                    ))}
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                    <BookOpen className="w-4 h-4" />
                  </div>
                </div>
                {(currentSession?.area?.toLowerCase() === 'geral' || !currentSession?.area) && (
                  <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20 font-bold uppercase tracking-wider">
                    Institucional
                  </span>
                )}
                {currentSession?.area && currentSession.area.toLowerCase() !== 'geral' && (
                  <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20 font-bold uppercase tracking-wider">
                    Base Especializada
                  </span>
                )}
              </div>
              
              <div className="flex items-center gap-4">
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 rounded-lg border border-slate-700/50">
                  <Cpu className="w-4 h-4 text-blue-400" />
                  <span className="text-xs text-slate-300 font-medium">Modelo UCDB-IA</span>
                </div>
                {currentSession && currentSession.messages.length > 0 && (
                  <button 
                    onClick={() => StorageService.exportSessionToTxt(currentSession)}
                    className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-blue-400 transition-colors bg-slate-800 px-2.5 py-1.5 rounded-md border border-slate-700"
                    title="Exportar conversa"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Exportar</span>
                  </button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {currentSession?.messages.map((msg) => (
                <div 
                  key={msg.id} 
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[80%] lg:max-w-[70%] ${msg.role === 'user' ? 'flex flex-row-reverse' : 'flex'} gap-4`}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                      msg.role === 'user' ? 'bg-slate-700' : 'bg-blue-600'
                    }`}>
                      {msg.role === 'user' ? <UserIcon className="w-5 h-5 text-slate-300" /> : <Bot className="w-5 h-5 text-white" />}
                    </div>

                    <div className="space-y-2 w-full">
                      <div className={`p-4 rounded-2xl ${
                        msg.role === 'user' 
                          ? 'bg-slate-800 text-slate-200 rounded-tr-none' 
                          : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none'
                      }`}>
                        {msg.role === 'assistant' ? (
                          <div 
                            className="prose prose-invert prose-sm max-w-none 
                              [&>p]:mb-3 [&>p]:leading-relaxed
                              [&>h1]:text-2xl [&>h1]:font-black [&>h1]:text-white [&>h1]:mb-2 [&>h1]:flex [&>h1]:items-center [&>h1]:gap-2
                              [&>h2]:text-xl [&>h2]:font-bold [&>h2]:text-blue-400 [&>h2]:mb-3 [&>h2]:mt-6
                              [&>h3]:text-lg [&>h3]:font-bold [&>h3]:text-blue-500 [&>h3]:mb-2 [&>h3]:mt-4 [&>h3]:flex [&>h3]:items-center [&>h3]:gap-2
                              [&>hr]:border-slate-800 [&>hr]:my-4
                              [&>p]:mb-3 [&>p]:leading-relaxed [&>p]:text-slate-300
                              [&>ul]:list-disc [&>ul]:pl-5 [&>ul]:mb-4
                              [&>ol]:list-decimal [&>ol]:pl-5 [&>ol]:mb-4
                              [&>pre]:bg-slate-950 [&>pre]:p-4 [&>pre]:rounded-lg [&>pre]:border [&>pre]:border-slate-800 [&>pre]:mb-4
                              [&>code]:bg-slate-800 [&>code]:px-1.5 [&>code]:py-0.5 [&>code]:rounded [&>code]:text-blue-300 [&>code]:text-xs"
                            dangerouslySetInnerHTML={renderMarkdown(msg.content)} 
                          />
                        ) : (
                          <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                        )}
                      </div>

                      {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                        <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800">
                          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1">
                            <BookOpen className="w-3 h-3" /> FONTES UTILIZADAS
                          </p>
                          <div className="grid gap-2">
                            {msg.citations.map((cite, idx) => (
                              <div key={idx} className="text-xs bg-slate-800 p-2 rounded border-l-2 border-blue-500 hover:bg-slate-700 transition-colors cursor-pointer group">
                                <a 
                                  href={cite.url} 
                                  target="_blank" 
                                  rel="noopener noreferrer" 
                                  className="font-medium text-blue-400 mb-1 hover:underline flex items-center gap-1"
                                >
                                  {cite.documentTitle}
                                  <ExternalLink className="w-3 h-3 opacity-50" />
                                </a>
                                <div className="text-slate-400 line-clamp-2 italic group-hover:text-slate-300">
                                  {cite.snippet}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {isProcessing && (
                <div className="flex justify-start">
                   <div className="flex gap-4 max-w-[80%]">
                    <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl rounded-tl-none flex items-center gap-2">
                      <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
                      <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></span>
                      <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></span>
                      <span className="text-xs text-slate-400 ml-2">Consultando base de conhecimento...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 bg-slate-900 border-t border-slate-800">
              <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto relative flex items-end">
                <div className="relative w-full">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Faça uma pergunta sobre os documentos..."
                    disabled={isProcessing}
                    rows={1}
                    className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl py-4 pl-6 pr-14 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 shadow-lg disabled:opacity-50 resize-none overflow-hidden max-h-[140px] overflow-y-auto block leading-normal"
                    style={{ minHeight: '58px' }}
                  />
                  <button 
                    type="submit" 
                    disabled={!input.trim() || isProcessing}
                    className="absolute right-3 bottom-3 p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </form>
              <div className="text-center mt-2 text-[10px] text-slate-600">
                UCDB-IA pode cometer erros. Verifique as fontes listadas.
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};