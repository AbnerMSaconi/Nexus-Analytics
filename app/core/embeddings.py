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
            # Timeout generoso para evitar falhas em textos longos
            response = requests.post(
                self.api_url,
                json={"content": text},
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            vector = []
            # 1. Tenta extrair do formato padrão
            if "embedding" in data:
                vector = data["embedding"]
            elif isinstance(data, list) and "embedding" in data[0]:
                vector = data[0]["embedding"]
            
            # 2. Validação e Correção de Formato (O PULO DO GATO)
            if not vector:
                raise ValueError("API retornou vetor vazio")

            # Se o servidor devolveu [[0.1, 0.2...]], pegamos apenas a lista interna
            if isinstance(vector, list) and len(vector) > 0 and isinstance(vector[0], list):
                vector = vector[0]

            return vector
        except Exception as e:
            logger.warning(f"⚠️ Erro ao vetorizar trecho: {e}")
            # Retorna lista vazia para ser filtrada depois, evitando crash da thread
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Usa ThreadPool para velocidade
        embeddings = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(self._get_single_embedding, texts))
            
            # Filtra falhas (vetores vazios) para não quebrar o FAISS
            # Se um falhar, o documento correspondente ficará sem vetor (melhor que crashar tudo)
            for res in results:
                if res:
                    embeddings.append(res)
                else:
                    # Fallback de emergência: vetor de zeros (não recomendado, mas evita crash)
                    # O ideal é que o text_splitter já tenha limpado chunks ruins
                    pass
                    
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        vec = self._get_single_embedding(text)
        if not vec:
            # Se falhar na query do usuário, retorna erro ou vetor zerado
            return [0.0] * 1024 # Ajuste o tamanho conforme seu modelo se necessário
        return vec

def get_embeddings():
    return LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)