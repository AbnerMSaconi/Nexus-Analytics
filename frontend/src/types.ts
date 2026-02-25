// frontend/src/types.ts

// --- Autenticação e Usuário ---
// --- Autenticação e Usuário ---
export interface User {
  id: string;
  username: string;
  full_name?: string; // Opcional, mas útil para exibir na tela
  role: string;
  course?: string;   
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
}

// --- Chat e Mensagens ---
export interface Citation {
  documentTitle: string;
  snippet: string;
  url?: string; // <--- O CAMPO NOVO QUE FALTAVA
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
}

export interface ChatSession {
  id: string;
  userId: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

// --- Gestão de Documentos ---
export interface Document {
  id: string;
  title: string;
  content: string;
  type: string;
  uploadDate: string;
}

export interface Folder {
  id: string;
  name: string;
  documents: Document[];
}