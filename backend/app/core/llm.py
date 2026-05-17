from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Any, List, Optional
import httpx
from app.utils.logger import logger
from app.core.config import settings
from app.utils.performance import monitor_perf
from functools import lru_cache

# Cliente global para monitoramento e pool de conexões
_shared_async_client = httpx.AsyncClient(
    timeout=120.0,
    limits=httpx.Limits(max_connections=5000, max_keepalive_connections=500)
)
_shared_sync_client = httpx.Client(
    timeout=120.0,
    limits=httpx.Limits(max_connections=1000, max_keepalive_connections=100)
)

@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """
    Retorna o motor de LLM (vLLM) configurado como ChatOpenAI por compatibilidade.
    Otimizado para alta concorrência e PagedAttention.
    """
    logger.info(f"🚀 Inicializando vLLM em: {settings.LLM_BASE_URL}")
    return ChatOpenAI(
        model=settings.MODEL_NAME, # Ex: "qwen2.5-3b-instruct"
        openai_api_key="empty",
        openai_api_base=str(settings.LLM_BASE_URL),
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        streaming=True,
        http_client=_shared_sync_client,
        http_async_client=_shared_async_client
    )

class LlamaServerLLM:
    """
    Mantido para retrocompatibilidade se necessário, mas get_llm agora usa ChatOpenAI.
    """
    pass
