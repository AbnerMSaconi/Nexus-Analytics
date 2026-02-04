# app/core/embeddings.py
from langchain_core.embeddings import Embeddings
import requests
from typing import List
from app.utils.logger import logger

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
            return data[0]["embedding"][0]
        except Exception as e:
            logger.error(f"✗ Falha ao gerar embedding de consulta: {e}")
            raise