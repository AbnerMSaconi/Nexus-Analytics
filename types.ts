export interface User {
  id: string;            // ID interno (uuid)
  username: string;      // ou external_id
  full_name?: string;
  role: string;          // 'aluno' | 'professor' | 'administrador' ...
  course?: string;       // 'Direito', 'Engenharia'...
  token?: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
}

export interface Document {
  id: string;
  title: string;
  type: 'pdf' | 'docx' | 'xlsx' | 'txt';
  category: string; // Corresponds to folder
  content: string; // Simulated extracted text
  uploadDate: Date;
}

export interface Folder {
  id: string;
  name: string;
  documents: Document[];
}

export interface Citation {
  documentId: string;
  documentTitle: string;
  snippet: string;
  relevanceScore: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  isLoading?: boolean;
}

export interface ChatSession {
  id: string;
  userId: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}