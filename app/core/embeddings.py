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
            # Corte rígido para modelos de 4B/3B que possuem contexto menor de embedding
            texto_seguro = text[:2000].strip()
            if not texto_seguro:
                return [0.0] * 1536
            
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
            elif isinstance(data, list) and len(data) > 0:
                vector = data[0] if isinstance(data[0], list) else data
            
            # Garante que o vetor seja uma lista simples de floats
            if isinstance(vector, list) and len(vector) > 0:
                if isinstance(vector[0], list):
                    vector = vector[0]
                
                # Converte todos os elementos para float
                return [float(x) for x in vector]
            
            return [0.0] * 1536
        except Exception as e:
            logger.warning(f"⚠️ Erro ao vetorizar trecho: {e}")
            return [0.0] * 1536

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(self._get_single_embedding, texts))
            
            # Validar consistência do tamanho (pega o tamanho do primeiro vetor válido)
            dim = 1536
            for r in results:
                if r and len(r) > 10: # Vetor válido
                    dim = len(r)
                    break

            for res in results:
                # Se o vetor veio errado ou vazio, ajustamos para a dimensão correta
                if not res or len(res) != dim:
                    embeddings.append([0.0] * dim)
                else:
                    embeddings.append(res)
                    
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        vec = self._get_single_embedding(text)
        # Busca a dimensão correta se o vetor falhar
        if not vec or len(vec) < 10:
            return [0.0] * 1536
        return vec

def get_embeddings():
    return LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)