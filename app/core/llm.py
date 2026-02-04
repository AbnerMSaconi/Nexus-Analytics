# app/core/llm.py
from langchain_core.language_models.llms import LLM
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
                "top_p": settings.TOP_P,
                "repeat_penalty": settings.REPETITION_PENALTY,
                "stop": stop_tokens,
                "stream": False,
            }
            
            # Logger opcional para debug
            # logger.debug(f"Enviando para LLM: {payload}")

            response = requests.post(
                f"{settings.LLM_BASE_URL}/completions",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            # Tratamento robusto da resposta
            data = response.json()
            if "content" in data: 
                return data["content"].strip()
            if "choices" in data:
                return data["choices"][0]["text"].strip()
                
            return str(data) # Fallback

        except Exception as e:
            logger.error(f"❌ Erro LLM: {e}")
            raise
    
    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"endpoint": settings.LLM_BASE_URL}

# --- FUNÇÃO QUE FALTAVA ---
def get_llm():
    """Retorna uma instância configurada do LLM."""
    return LlamaServerLLM()