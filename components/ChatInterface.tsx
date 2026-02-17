import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User as UserIcon, BookOpen, Clock, Plus, Cpu, AlertTriangle } from 'lucide-react';
import { generateRAGResponse } from '../services/geminiService';
import { StorageService } from '../services/storageService';
import type { Message, ChatSession, User } from '../types';

interface ChatInterfaceProps {
  user: User;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ user }) => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadSessions();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

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

  const currentSession = sessions.find(s => s.id === currentSessionId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentSession?.messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    // Update UI immediately
    const updatedSession = { 
      ...currentSession!, 
      messages: [...(currentSession!.messages), userMsg],
      updatedAt: new Date()
    };
    
    // Update title if it's the first message
    if (updatedSession.messages.length === 1) {
      updatedSession.title = input.substring(0, 30) + (input.length > 30 ? '...' : '');
    }

    setSessions(prev => prev.map(s => s.id === currentSessionId ? updatedSession : s));
    await StorageService.saveSession(updatedSession);
    setInput('');
    setIsProcessing(true);

    // RAG PROCESS
    try {
      // 1. Fetch Knowledge Base
      const allDocs = await StorageService.getAllDocuments();
      
      // 2. Generate Answer with Context
      const aiResponse = await generateRAGResponse(userMsg.content, allDocs);

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

    } catch (error) {
      console.error(error);
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
            className="w-full bg-primary hover:bg-blue-600 text-white rounded-lg py-2 flex items-center justify-center gap-2 transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" /> Nova Conversa
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2">
          {sessions.map(session => (
            <button
              key={session.id}
              onClick={() => setCurrentSessionId(session.id)}
              className={`w-full text-left p-3 rounded-lg mb-1 text-sm flex items-center gap-3 transition-colors ${
                currentSessionId === session.id 
                  ? 'bg-slate-800 text-white border border-slate-700' 
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
              }`}
            >
              <Clock className="w-4 h-4 min-w-[16px]" />
              <span className="truncate">{session.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-background relative">
        {!currentSessionId ? (
          <div className="flex-1 flex items-center justify-center text-slate-500">
            Selecione ou inicie uma conversa.
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="h-14 border-b border-slate-700 flex items-center justify-between px-6 bg-slate-900/50 backdrop-blur">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-accent" />
                <span className="text-slate-200 font-medium">{currentSession?.title}</span>
              </div>
              <div className="text-xs text-slate-500 flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                RAG Engine Online
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
                      msg.role === 'user' ? 'bg-slate-700' : 'bg-primary'
                    }`}>
                      {msg.role === 'user' ? <UserIcon className="w-5 h-5 text-slate-300" /> : <Bot className="w-5 h-5 text-white" />}
                    </div>

                    <div className="space-y-2">
                      <div className={`p-4 rounded-2xl ${
                        msg.role === 'user' 
                          ? 'bg-slate-800 text-slate-200 rounded-tr-none' 
                          : 'bg-surface border border-slate-700 text-slate-200 rounded-tl-none'
                      }`}>
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      </div>

                      {/* Sources / Citations */}
                      {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                        <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800">
                          <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1">
                            <BookOpen className="w-3 h-3" /> FONTES UTILIZADAS
                          </p>
                          <div className="grid gap-2">
                            {msg.citations.map((cite, idx) => (
                              <div key={idx} className="text-xs bg-slate-800 p-2 rounded border-l-2 border-accent hover:bg-slate-700 transition-colors cursor-pointer group">
                                <div className="font-medium text-accent mb-1">{cite.documentTitle}</div>
                                <div className="text-slate-400 line-clamp-2 italic group-hover:text-slate-300">"{cite.snippet}"</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {msg.role === 'assistant' && (!msg.citations || msg.citations.length === 0) && (
                        <div className="flex items-center gap-1 text-xs text-yellow-500/80">
                            <AlertTriangle className="w-3 h-3"/> Resposta gerada sem contexto específico encontrado.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {isProcessing && (
                <div className="flex justify-start">
                   <div className="flex gap-4 max-w-[80%]">
                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
                      <Bot className="w-5 h-5 text-white" />
                    </div>
                    <div className="bg-surface border border-slate-700 p-4 rounded-2xl rounded-tl-none flex items-center gap-2">
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

            {/* Input Area */}
            <div className="p-4 bg-slate-900 border-t border-slate-700">
              <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Faça uma pergunta sobre os documentos..."
                  disabled={isProcessing}
                  className="w-full bg-surface border border-slate-700 text-white rounded-xl py-4 pl-6 pr-14 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary shadow-lg disabled:opacity-50"
                />
                <button 
                  type="submit" 
                  disabled={!input.trim() || isProcessing}
                  className="absolute right-3 top-3 p-2 bg-primary hover:bg-blue-600 text-white rounded-lg transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed"
                >
                  <Send className="w-5 h-5" />
                </button>
              </form>
              <div className="text-center mt-2 text-[10px] text-slate-600">
                Nexus AI pode cometer erros. Verifique as fontes listadas.
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};