import { GoogleGenAI } from "@google/genai";
import { Document, Citation } from "../types";

// In a production environment, this would be an API call to a local Python backend (LlamaIndex/LangChain)
// For this React prototype, we use Gemini to simulate the "Reasoning" phase after we manually filter context.

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

// Heuristic similarity search simulation (Client-side RAG for demo)
// In production, this is replaced by a Vector DB query (ChromaDB/Pinecone/PgVector)
const findRelevantContext = (query: string, documents: Document[]): Citation[] => {
  const queryTerms = query.toLowerCase().split(' ').filter(t => t.length > 3);
  const hits: Citation[] = [];

  documents.forEach(doc => {
    let score = 0;
    const lowerContent = doc.content.toLowerCase();
    
    queryTerms.forEach(term => {
      if (lowerContent.includes(term)) score += 1;
    });

    if (score > 0) {
      // Extract a snippet around the first match
      const firstMatchIndex = lowerContent.indexOf(queryTerms[0]);
      const start = Math.max(0, firstMatchIndex - 50);
      const end = Math.min(doc.content.length, firstMatchIndex + 200);
      const snippet = doc.content.substring(start, end) + "...";

      hits.push({
        documentId: doc.id,
        documentTitle: doc.title,
        snippet: snippet,
        relevanceScore: score
      });
    }
  });

  return hits.sort((a, b) => b.relevanceScore - a.relevanceScore).slice(0, 3);
};

export const generateRAGResponse = async (
  query: string,
  allDocuments: Document[]
): Promise<{ text: string; citations: Citation[] }> => {
  try {
    // 1. Retrieval Phase
    const citations = findRelevantContext(query, allDocuments);

    if (citations.length === 0) {
      return {
        text: "Não encontrei informações relevantes nos documentos internos para responder a essa pergunta.",
        citations: []
      };
    }

    // 2. Augmentation Phase
    const contextText = citations.map(c => 
      `Documento: "${c.documentTitle}"\nTrecho: "...${c.snippet}..."`
    ).join("\n\n");

    const systemPrompt = `
      Você é um assistente de IA corporativo seguro e preciso.
      Sua tarefa é responder perguntas baseadas ESTRITAMENTE no contexto fornecido abaixo.
      
      Regras:
      1. Se a resposta não estiver no contexto, diga que não sabe. NÃO invente informações.
      2. Cite o nome do documento ao mencionar fatos específicos.
      3. Mantenha um tom profissional.
      4. Responda em Português.
      
      --- CONTEXTO ENCONTRADO ---
      ${contextText}
      ---------------------------
    `;

    // 3. Generation Phase
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: [
        { role: 'user', parts: [{ text: systemPrompt }] },
        { role: 'user', parts: [{ text: `Pergunta do usuário: ${query}` }] }
      ]
    });

    return {
      text: response.text || "Erro ao gerar resposta.",
      citations
    };

  } catch (error) {
    console.error("Gemini RAG Error:", error);
    return {
      text: "Desculpe, ocorreu um erro ao processar sua solicitação no sistema RAG.",
      citations: []
    };
  }
};