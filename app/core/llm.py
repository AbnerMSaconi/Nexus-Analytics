from langchain_core.language_models.llms import LLM
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import CallbackManagerForLLMRun
from typing import Any, List, Optional
import httpx
import asyncio
from app.utils.logger import logger
from app.core.config import settings

from app.utils.performance import monitor_perf

# Cliente global com pool de conexões para alta concorrência (5000+)
_shared_client = httpx.AsyncClient(
    timeout=120.0,
    limits=httpx.Limits(max_connections=5000, max_keepalive_connections=500)
)

class LlamaServerLLM(LLM):
    @property
    def _llm_type(self) -> str:
        return "llama_server"

    @monitor_perf("Inferência LLM (Model Server)")
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stop_tokens = stop or []
                if "<|im_end|>" not in stop_tokens:
                    stop_tokens.append("<|im_end|>")

                payload = {
                    "prompt": prompt,
                    "temperature": settings.TEMPERATURE,
                    "max_tokens": settings.MAX_TOKENS,
                    "stop": stop_tokens,
                    "stream": False,
                }

                response = await _shared_client.post(
                    f"{settings.LLM_BASE_URL}/completions",
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                if "content" in data: return data["content"].strip()
                if "choices" in data: return data["choices"][0]["text"].strip()
                return str(data)

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"🔄 Tentativa {attempt + 1} do LLM falhou, tentando novamente... ({e})")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"❌ Erro crítico no LLM após {max_retries} tentativas: {e}")
                    raise

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        # Fallback para chamadas síncronas se necessário, mas prefira _acall
        import requests
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stop_tokens = stop or []
                if "<|im_end|>" not in stop_tokens:
                    stop_tokens.append("<|im_end|>")

                payload = {
                    "prompt": prompt,
                    "temperature": settings.TEMPERATURE,
                    "max_tokens": settings.MAX_TOKENS,
                    "stop": stop_tokens,
                    "stream": False,
                }

                response = requests.post(
                    f"{settings.LLM_BASE_URL}/completions",
                    json=payload,
                    timeout=120
                )
                response.raise_for_status()
                
                data = response.json()
                if "content" in data: return data["content"].strip()
                if "choices" in data: return data["choices"][0]["text"].strip()
                return str(data)

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"🔄 Tentativa {attempt + 1} do LLM falhou, tentando novamente... ({e})")
                    time.sleep(1)
                else:
                    logger.error(f"❌ Erro crítico no LLM após {max_retries} tentativas: {e}")
                    raise
    
    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"endpoint": settings.LLM_BASE_URL}

def get_llm():
    """
    Retorna uma instância de ChatOpenAI configurada para o servidor local.
    A conversão para str() é necessária para compatibilidade com AnyHttpUrl do Pydantic.
    """
    return ChatOpenAI(
        base_url=str(settings.LLM_BASE_URL),
        api_key="sk-no-key", 
        max_tokens=settings.MAX_TOKENS,
        temperature=settings.TEMPERATURE
    )
