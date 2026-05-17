from langchain_core.embeddings import Embeddings
import httpx
import asyncio
from typing import List, Any
from app.utils.logger import logger
from app.core.config import settings
from app.utils.performance import monitor_perf

# Cliente global com pool de conexões para alta concorrência (5000+)
_emb_client = httpx.AsyncClient(
    timeout=120.0,
    limits=httpx.Limits(max_connections=5000, max_keepalive_connections=500)
)

class LlamaEmbeddings(Embeddings):
    def __init__(self, api_url: Any):
        self.api_url = str(api_url).strip() # Remove espaços acidentais
        self.dimension = 1536 # Default inicial
        logger.info(f"🧬 LlamaEmbeddings configurado para: {self.api_url}")

    async def _get_single_embedding_async(self, client: httpx.AsyncClient, text: str) -> List[float]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                texto_seguro = text[:2000].strip()
                if not texto_seguro:
                    return [0.0] * self.dimension
                
                response = await client.post(
                    self.api_url,
                    json={"content": texto_seguro}
                )
                response.raise_for_status()
                data = response.json()
                
                vector = []
                if isinstance(data, dict):
                    if "embedding" in data:
                        vector = data["embedding"]
                    elif "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                        item = data["data"][0]
                        vector = item.get("embedding", []) if isinstance(item, dict) else []
                elif isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], list):
                        vector = data[0]
                    elif isinstance(data[0], dict):
                        vector = data[0].get("embedding", [])
                    else:
                        vector = data
                
                if isinstance(vector, list) and len(vector) > 0:
                    if isinstance(vector[0], list):
                        vector = vector[0]
                    try:
                        res = [float(x) for x in vector if not isinstance(x, dict)]
                        if len(res) > 10:
                            self.dimension = len(res)
                        return res
                    except (ValueError, TypeError) as e:
                        logger.warning(f"⚠️ Erro ao converter elementos do vetor: {e}")
                        return [0.0] * self.dimension
                
                return [0.0] * self.dimension

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"🔄 Tentativa {attempt + 1} falhou para embedding, tentando novamente... ({e})")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"⚠️ Erro final ao vetorizar trecho após {max_retries} tentativas: {e}")
                    return [0.0] * self.dimension

    @monitor_perf("Vetorização de Documentos (Embeddings)")
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        # Limitamos a concorrência para não estourar a RAM/Socket do servidor
        semaphore = asyncio.Semaphore(32)
        
        async def sem_task(text):
            async with semaphore:
                return await self._get_single_embedding_async(_emb_client, text)

        tasks = [sem_task(text) for text in texts]
        results = await asyncio.gather(*tasks)
        
        dim = self.dimension
        for r in results:
            if r and len(r) > 10:
                dim = len(r)
                self.dimension = dim
                break

        embeddings = []
        for res in results:
            if not res or len(res) != dim:
                embeddings.append([0.0] * dim)
            else:
                embeddings.append(res)
        return embeddings

    @monitor_perf("Vetorização de Pergunta (Query Embedding)")
    async def aembed_query(self, text: str) -> List[float]:
        vec = await self._get_single_embedding_async(_emb_client, text)
        if not vec or len(vec) < 10:
            return [0.0] * self.dimension
        return vec

    def _get_single_embedding(self, text: str) -> List[float]:
        import requests
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Corte rígido para modelos de 4B/3B que possuem contexto menor de embedding
                texto_seguro = text[:2000].strip()
                if not texto_seguro:
                    return [0.0] * self.dimension
                
                response = requests.post(
                    self.api_url,
                    json={"content": texto_seguro},
                    timeout=120
                )
                response.raise_for_status()
                data = response.json()
                
                vector = []
                # 1. Formato direto: {"embedding": [...]}
                if isinstance(data, dict):
                    if "embedding" in data:
                        vector = data["embedding"]
                    elif "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                        # Formato OpenAI: {"data": [{"embedding": [...]}, ...]}
                        item = data["data"][0]
                        vector = item.get("embedding", []) if isinstance(item, dict) else []
                
                # 2. Formato de lista: [...] ou [[...]] ou [{"embedding": [...]}]
                elif isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], list):
                        vector = data[0]
                    elif isinstance(data[0], dict):
                        vector = data[0].get("embedding", [])
                    else:
                        vector = data
                
                # Garante que o vetor seja uma lista simples de floats
                if isinstance(vector, list) and len(vector) > 0:
                    # Caso especial: se ainda for uma lista de listas
                    if isinstance(vector[0], list):
                        vector = vector[0]
                    
                    # Converte apenas se for número ou string conversível, ignora dicts
                    try:
                        res = [float(x) for x in vector if not isinstance(x, dict)]
                        if len(res) > 10:
                            self.dimension = len(res) # Atualiza a dimensão real do modelo
                        return res
                    except (ValueError, TypeError) as e:
                        logger.warning(f"⚠️ Erro ao converter elementos do vetor: {e}")
                        return [0.0] * self.dimension
                
                return [0.0] * self.dimension

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"🔄 Tentativa {attempt + 1} falhou para embedding, tentando novamente... ({e})")
                    import time
                    time.sleep(1) # Pequena pausa antes de tentar novamente
                else:
                    logger.error(f"⚠️ Erro final ao vetorizar trecho após {max_retries} tentativas: {e}")
                    return [0.0] * self.dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import concurrent.futures
        embeddings = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(self._get_single_embedding, texts))
            
            # Validar consistência do tamanho (pega o tamanho do primeiro vetor válido)
            dim = self.dimension
            for r in results:
                if r and len(r) > 10: # Vetor válido
                    dim = len(r)
                    self.dimension = dim
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
            return [0.0] * self.dimension
        return vec

def get_embeddings():
    return LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)