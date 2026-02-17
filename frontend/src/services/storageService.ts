import type { ChatSession, Folder, Document } from '../types';

// Configuração centralizada da API (Padrão Vite)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const StorageService = {
  /**
   * Recupera as sessões salvas.
   */
  async getSessions(userId: string): Promise<ChatSession[]> {
    try {
      const data = localStorage.getItem(`sessions_${userId}`);
      if (!data) return [];
      return JSON.parse(data);
    } catch (error) {
      console.error(`[StorageService] Erro ao analisar sessões:`, error);
      return [];
    }
  },

  async saveSession(session: ChatSession): Promise<void> {
    try {
      const sessions = await this.getSessions(session.userId);
      const index = sessions.findIndex(s => s.id === session.id);
      
      if (index > -1) {
        sessions[index] = session;
      } else {
        sessions.unshift(session);
      }
      
      localStorage.setItem(`sessions_${session.userId}`, JSON.stringify(sessions));
      window.dispatchEvent(new Event('storage'));
    } catch (error) {
      console.error("[StorageService] Falha ao salvar sessão:", error);
    }
  },

  // --- NOVA FUNÇÃO DE EXCLUSÃO ---
  async deleteSession(sessionId: string, userId: string): Promise<void> {
    try {
      const sessions = await this.getSessions(userId);
      const newSessions = sessions.filter(s => s.id !== sessionId);
      localStorage.setItem(`sessions_${userId}`, JSON.stringify(newSessions));
      window.dispatchEvent(new Event('storage'));
      
      // Opcional: Tenta deletar do backend também se houver token (Futuro)
      // const token = localStorage.getItem('nexus_token');
      // if(token) fetch(`${API_BASE_URL}/conversations/${sessionId}`, { method: 'DELETE', ... })
      
    } catch (error) {
      console.error("[StorageService] Falha ao excluir sessão:", error);
    }
  },

  async getFolders(): Promise<Folder[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/knowledge-areas`);
      if (!res.ok) throw new Error(`Erro HTTP: ${res.status}`);
      const data = await res.json();
      
      return data.areas.map((area: string) => ({
        id: area.toLowerCase().replace(/\s+/g, '-'),
        name: area,
        documents: [] 
      }));
    } catch (error) {
      console.error("[StorageService] Erro ao buscar áreas:", error);
      return [];
    }
  },

  async getAllDocuments(): Promise<Document[]> {
    return [];
  }
};