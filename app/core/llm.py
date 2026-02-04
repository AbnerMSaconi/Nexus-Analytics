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
            # ADICIONA STOP TOKEN DO HERMES/CHATML
            stop_tokens = stop or []
            if "<|im_end|>" not in stop_tokens:
                stop_tokens.append("<|im_end|>")

            response = requests.post(
                f"{settings.LLM_BASE_URL}/completions",
                json={
                    "prompt": prompt,
                    "temperature": settings.TEMPERATURE,
                    "max_tokens": 4096, # Llama 3.1 aguenta respostas longas
                    "top_p": settings.TOP_P,
                    "repeat_penalty": settings.REPETITION_PENALTY,
                    "stop": stop_tokens,
                    "stream": False,
                },
                timeout=120
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["text"].strip()
            return text

        except Exception as e:
            logger.error(f"❌ Erro LLM: {e}")
            raise
    
    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"endpoint": settings.LLM_BASE_URL}