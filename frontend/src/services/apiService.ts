import { api } from '../assets/api';

// URL base do backend (ajuste se estiver rodando em outro IP)
const BACKEND_URL = "http://127.0.0.1:8000";

export interface RAGResponse {
  text: string;
  citations: { documentTitle: string; snippet: string; url?: string }[];
}

export const generateRAGResponse = async (
  message: string, 
  area: string = "Geral", 
  token: string | null = null
): Promise<RAGResponse> => {
  
  const response = await api.chatStream(message, area, token);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Erro na comunicação com o Llama local');
  }
  
  if (!response.body) throw new Error('ReadableStream não suportado.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullText = "";
  let sources: any[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n\n');

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const jsonStr = line.substring(6).trim();
          if (!jsonStr) continue;
          
          const data = JSON.parse(jsonStr);

          if (data.type === 'chunk') {
            fullText += data.content;
          } 
          else if (data.type === 'sources') {
            // Backend agora envia: [{filename, area, topic}, ...]
            sources = data.content;
          }
          else if (data.type === 'error') {
            throw new Error(data.content);
          }
        } catch (e) {
          console.warn("Erro ao processar chunk:", e);
        }
      }
    }
  }

  // Mapeamento Final para o Chat
  return {
    text: fullText,
    citations: sources.map((src: any) => {
      // Usa o caminho relativo exato enviado pelo backend
      // Se src.filepath for "Saude/doc.pdf", o link vira ".../pdfs/Saude/doc.pdf"
      // Se for "doc.pdf", vira ".../pdfs/doc.pdf"
      const rawPath = `/pdfs/${src.filepath || src.filename}`;

      const encodedUrl = `${BACKEND_URL}${encodeURI(rawPath).replace(/%5C/g, '/')}`; // Corrige barras invertidas do Windows se houver

      return {
        documentTitle: src.filename,
        snippet: src.topic || "Documento Referenciado",
        url: encodedUrl
      };
    })
  };
};            