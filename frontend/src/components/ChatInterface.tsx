import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User as UserIcon, BookOpen, Clock, Plus, Cpu, Trash2, ExternalLink, Download } from 'lucide-react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { generateRAGResponse } from "../services/apiService";
import { StorageService } from '../services/storageService';
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
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null); // REF PARA O TEXTAREA

  useEffect(() => {
    loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  useEffect(() => {
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise().catch((err: any) => console.log('MathJax error:', err));
    }
  }, [sessions, isProcessing]);

  // EFEITO DE AUTOGROW (Crescimento Automático)
  useEffect(() => {
    if (textareaRef.current) {
      // 1. Reseta a altura para calcular o scrollHeight real (caso apague texto)
      textareaRef.current.style.height = 'auto';
      
      // 2. Define a nova altura baseada no conteúdo, limitando visualmente via CSS max-h
      // O scrollHeight inclui o padding. 
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const loadSessions = async () => {
    const loadedSessions = await StorageService.getSessions(user.id);
    setSessions(loadedSessions);
    if (loadedSessions.length > 0 && !currentSessionId) {
      setCurrentSessionId(loadedSessions[0].id);
    } else if (loadedSessions.length === 0) {
      createNewSession();
    }
  };

  const createNewSession = async () => {
    const newSession: ChatSession = {
      id: crypto.randomUUID(),
      userId: user.id,
      title: 'Nova Conversa',
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date()
    };
    await StorageService.saveSession(newSession);
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
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
      // 1. Protege blocos de MathJax para que o marked não os corrompa
      const mathBlocks: string[] = [];
      const tempContent = content.replace(/(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\))/gs, (match) => {
        mathBlocks.push(match);
        return `@@MATHBLOCK${mathBlocks.length - 1}@@`;
      });

      // 2. Converte o Markdown para HTML
      const html = marked.parse(tempContent, { async: false }) as string;

      // 3. Sanitiza o HTML com os placeholders ainda neles (seguro)
      const cleanHtml = DOMPurify.sanitize(html);

      // 4. Restaura as fórmulas originais NO HTML LIMPO
      // Isso evita que o DOMPurify delete fórmulas que usem < ou >
      const finalHtml = cleanHtml.replace(/@@MATHBLOCK(\d+)@@/g, (_, id) => {
        return mathBlocks[parseInt(id)];
      });

      return { __html: finalHtml };
    } catch (e) {
      return { __html: content };
    }
  };

  // Efeito para re-processar MathJax sempre que as mensagens mudarem ou o processamento terminar
  useEffect(() => {
    if (window.MathJax && window.MathJax.typesetPromise) {
      // Pequeno delay para garantir que o DOM foi atualizado pelo React
      setTimeout(() => {
        window.MathJax.typesetPromise().catch((err: any) => console.log('MathJax error:', err));
      }, 100);
    }
  }, [sessions, isProcessing, currentSessionId]);

  // HANDLER PARA TECLA ENTER
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Se apertar Enter (sem Shift) e tiver texto, envia
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault(); // Evita pular linha
      if (input.trim() && !isProcessing) {
        // Dispara o evento de submit do formulário manualmente
        handleSendMessage(e as unknown as React.FormEvent);
      }
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId) return;
    
    const userText = input;
    setInput('');
    setIsProcessing(true);

    // Reseta altura do textarea forçadamente após envio
    if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      timestamp: new Date()
    };

    const sessionToUpdate = sessions.find(s => s.id === currentSessionId);
    if (!sessionToUpdate) return;

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
      
      // === NOVA LÓGICA DE ROTEAMENTO DE PERSONA ===
      let areaSolicitada = "Geral"; // Fallback padrão
      
      if (user.course) {
        const cursoNormalizado = user.course.toLowerCase();
        
        // Mapeia o curso do aluno para o banco de dados vetorial correspondente
        if (cursoNormalizado.includes("engenharia") || cursoNormalizado.includes("arquitetura")) {
          areaSolicitada = "engenharia";
        } else if (cursoNormalizado.includes("direito")) {
          areaSolicitada = "direito";
        } else if (cursoNormalizado.includes("tecnologia") || cursoNormalizado.includes("computa") || cursoNormalizado.includes("sistemas")) {
          areaSolicitada = "tecnologia";
        } else if (cursoNormalizado.includes("saude") || cursoNormalizado.includes("medicina") || cursoNormalizado.includes("enfermagem") || cursoNormalizado.includes("veterinaria")) {
          areaSolicitada = "saude";
        } else {
          areaSolicitada = user.course; 
        }
      }

      // Agora sim, chamamos a API passando a área correta do aluno!
      const aiResponse = await generateRAGResponse(userText, areaSolicitada, token);
      // =============================================

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
            {/* Header */}
            <div className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50 backdrop-blur">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-blue-400" />
                <span className="text-slate-200 font-medium">{currentSession?.title}</span>
              </div>
              <div className="flex items-center gap-4">
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
                <div className="text-xs text-slate-500 flex items-center gap-1">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                  RAG Engine Online
                </div>
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
                            className="prose prose-invert prose-sm max-w-none [&>p]:mb-2 [&>ul]:list-disc [&>ul]:pl-4 [&>ol]:list-decimal [&>ol]:pl-4 [&>pre]:bg-slate-950 [&>pre]:p-2 [&>pre]:rounded [&>code]:bg-slate-800 [&>code]:px-1 [&>code]:rounded"
                            dangerouslySetInnerHTML={renderMarkdown(msg.content)} 
                          />
                        ) : (
                          <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                        )}
                      </div>

                      {/* AREA DE CITAÇÕES */}
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

            {/* Input Area (Agora com Textarea Auto-Grow) */}
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
                    style={{ minHeight: '58px' }} // Altura mínima consistente
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