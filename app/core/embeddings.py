from langchain_core.embeddings import Embeddings
import requests
from typing import List, Any
from app.utils.logger import logger
from app.core.config import settings
import concurrent.futures

class LlamaEmbeddings(Embeddings):
    def __init__(self, api_url: str):
        self.api_url = api_url

    def _get_single_embedding(self, text: str) -> List[float]:
        try:
            # 1. BLINDAGEM DE CONTEXTO: Força um limite absoluto de caracteres.
            # Se um PDF tiver lixo sem espaços, cortamos na marra para não dar Erro 500 no Nomic.
            texto_seguro = text[:5000] 
            
            response = requests.post(
                self.api_url,
                json={"content": texto_seguro},
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            vector = []
            if "embedding" in data:
                vector = data["embedding"]
            elif isinstance(data, list) and "embedding" in data[0]:
                vector = data[0]["embedding"]
            
            if not vector:
                raise ValueError("API retornou vetor vazio")

            if isinstance(vector, list) and len(vector) > 0 and isinstance(vector[0], list):
                vector = vector[0]

            return vector
        except Exception as e:
            logger.warning(f"⚠️ Erro ao vetorizar trecho: {e}")
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        
        # 2. DIMINUIMOS A PRESSÃO: 3 workers dão respiro para o Llama.cpp e a GPU
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(self._get_single_embedding, texts))
            
            # 3. BLINDAGEM DO FAISS: O tamanho de texts DEVE ser igual ao de embeddings.
            for res in results:
                if res:
                    embeddings.append(res)
                else:
                    # O Nomic usa 768 dimensões. Se falhar, injetamos um vetor "neutro" cheio de zeros.
                    # Isso impede que o FAISS crashe e apenas ignora aquele trecho corrompido na busca.
                    embeddings.append([0.0] * 768)
                    
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        vec = self._get_single_embedding(text)
        if not vec:
            return [0.0] * 768 
        return vec

def get_embeddings():
    return LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)