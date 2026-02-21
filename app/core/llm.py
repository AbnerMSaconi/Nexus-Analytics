from langchain_core.language_models.llms import LLM
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import CallbackManagerForLLMRun
from typing import Any, List, Optional
import requests
from app.utils.logger import logger
from app.core.config import settings

class LlamaServerLLM(LLM):
    @property
    def _llm_type(self) -> str:
        return "llama_server"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        try:
            stop_tokens = stop or []
            if "<|im_end|>" not in stop_tokens:
                stop_tokens.append("<|im_end|>")

            payload = {
                "prompt": prompt,
                "temperature": settings.TEMPERATURE,
                "max_tokens": 4096,
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
            logger.error(f"Erro LLM: {e}")
            raise
    
    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"endpoint": settings.LLM_BASE_URL}



def get_llm():
    return ChatOpenAI(
        base_url=str(settings.LLM_BASE_URL), # <--- A CORREÇÃO É AQUI (adicionar str())
        api_key="sk-no-key", 
        max_tokens=settings.MAX_TOKENS,
        temperature=settings.TEMPERATURE
    )