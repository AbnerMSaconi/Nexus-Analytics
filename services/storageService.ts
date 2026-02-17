import { Document, Folder, ChatSession, User } from '../types';

// Initial Mock Data
const MOCK_FOLDERS: Folder[] = [
  {
    id: 'f1',
    name: 'Financeiro',
    documents: [
      {
        id: 'd1',
        title: 'Relatório Anual 2023.pdf',
        type: 'pdf',
        category: 'Financeiro',
        content: 'O lucro líquido da empresa em 2023 foi de R$ 5.4 milhões, um aumento de 12% em relação ao ano anterior. As despesas operacionais foram reduzidas em 5% devido à nova política de home office.',
        uploadDate: new Date()
      },
      {
        id: 'd2',
        title: 'Balanço Q1 2024.xlsx',
        type: 'xlsx',
        category: 'Financeiro',
        content: 'No primeiro trimestre de 2024, o EBITDA atingiu R$ 1.2 milhões. O setor de tecnologia representou 40% do faturamento total.',
        uploadDate: new Date()
      }
    ]
  },
  {
    id: 'f2',
    name: 'Jurídico',
    documents: [
      {
        id: 'd3',
        title: 'Contrato de Prestação de Serviços - Alpha.docx',
        type: 'docx',
        category: 'Jurídico',
        content: 'Cláusula 4: O presente contrato tem vigência de 12 meses, renovável automaticamente por iguais períodos, salvo manifestação contrária com 30 dias de antecedência. Multa rescisória de 10% do valor restante.',
        uploadDate: new Date()
      }
    ]
  },
  {
    id: 'f3',
    name: 'Recursos Humanos',
    documents: [
      {
        id: 'd4',
        title: 'Política de Benefícios.pdf',
        type: 'pdf',
        category: 'Recursos Humanos',
        content: 'Todos os colaboradores efetivos têm direito a vale-refeição de R$ 45,00 por dia útil e plano de saúde com coparticipação de 20%.',
        uploadDate: new Date()
      }
    ]
  }
];

// Helper to simulate encryption/decryption delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const StorageService = {
  getFolders: async (): Promise<Folder[]> => {
    await delay(300); // Simulate network/disk IO
    const stored = localStorage.getItem('nexus_folders');
    return stored ? JSON.parse(stored) : MOCK_FOLDERS;
  },

  getAllDocuments: async (): Promise<Document[]> => {
    const folders = await StorageService.getFolders();
    return folders.flatMap(f => f.documents);
  },

  saveDocument: async (folderId: string, doc: Document): Promise<void> => {
    const folders = await StorageService.getFolders();
    const updatedFolders = folders.map(f => {
      if (f.id === folderId) {
        return { ...f, documents: [...f.documents, doc] };
      }
      return f;
    });
    localStorage.setItem('nexus_folders', JSON.stringify(updatedFolders));
  },

  getSessions: async (userId: string): Promise<ChatSession[]> => {
    await delay(200);
    const stored = localStorage.getItem(`nexus_sessions_${userId}`);
    return stored ? JSON.parse(stored) : [];
  },

  saveSession: async (session: ChatSession): Promise<void> => {
    const sessions = await StorageService.getSessions(session.userId);
    const existingIndex = sessions.findIndex(s => s.id === session.id);
    
    let newSessions;
    if (existingIndex >= 0) {
      newSessions = [...sessions];
      newSessions[existingIndex] = session;
    } else {
      newSessions = [session, ...sessions];
    }
    
    localStorage.setItem(`nexus_sessions_${session.userId}`, JSON.stringify(newSessions));
  }
};