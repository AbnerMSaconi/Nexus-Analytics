# app/core/embeddings.py
from langchain_core.embeddings import Embeddings
import requests
from typing import List
from app.utils.logger import logger
from app.core.config import settings  # Importação necessária

class LlamaEmbeddings(Embeddings):
    def __init__(self, api_url: str):
        self.api_url = api_url

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = []
            for text in texts:
                response = requests.post(
                    self.api_url,
                    json={"content": text},
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                # Ajuste conforme o formato de resposta do seu servidor de embeddings
                if "embedding" in data:
                     embeddings.append(data["embedding"])
                elif isinstance(data, list) and "embedding" in data[0]:
                     embeddings.append(data[0]["embedding"][0])
                else:
                    # Fallback genérico
                     embeddings.append(data[0]["embedding"][0])

            logger.info(f"✓ Embeddings gerados para {len(texts)} documentos")
            return embeddings
        except Exception as e:
            logger.error(f"✗ Falha ao gerar embeddings: {e}")
            raise

    def embed_query(self, text: str) -> List[float]:
        try:
            response = requests.post(
                self.api_url,
                json={"content": text},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            # Ajuste de parsing igual ao embed_documents
            if "embedding" in data:
                 return data["embedding"]
            return data[0]["embedding"][0]
        except Exception as e:
            logger.error(f"✗ Falha ao gerar embedding de consulta: {e}")
            raise

# --- FUNÇÃO QUE FALTAVA ---
def get_embeddings():
    """Retorna uma instância configurada dos embeddings."""
    return LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)