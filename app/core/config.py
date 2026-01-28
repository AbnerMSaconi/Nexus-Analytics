# app/core/config.py
from pydantic_settings import SettingsConfigDict, BaseSettings
from pydantic import AnyHttpUrl
import os
import secrets

class Settings(BaseSettings):
    # API
    APP_NAME: str = "UCDB Chat"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    SECRET_KEY: str = secrets.token_hex(32)

    # LLM
    LLM_BASE_URL: AnyHttpUrl = "http://localhost:8080/v1"
    EMBEDDING_API_URL: AnyHttpUrl = "http://localhost:8081/embedding"
    MAX_TOKENS: int = 15500
    TEMPERATURE: float = 0.85
    TOP_P: float = 0.9
    REPETITION_PENALTY: float = 1

    # RAG
    CHUNK_SIZE: int = 812
    CHUNK_OVERLAP: int = 64
    RETRIEVAL_K: int = 7

    # --- CONFIGURAÇÃO DE MODELOS LOCAIS ---
    # Diretório onde os arquivos .gguf estão localizados
    MODELS_DIR: str = os.path.expanduser("~/.cache/llama.cpp")

    # Comando para iniciar o Qwen Embeddings (Porta 8081)
    CMD_EMBEDDING: list = [
        "llama-server",
        "-m", "Qwen_Qwen3-Embedding-0.6B-GGUF_Qwen3-Embedding-0.6B-Q8_0.gguf",
        "--embedding",
        "--port", "8081"
    ]

    # Comando para iniciar o GLM LLM (Porta 8080)
    CMD_LLM: list = [
        "llama-server",
        "-m", "unsloth_GLM-4-9B-0414-GGUF_GLM-4-9B-0414-Q4_K_M.gguf",
        "--port", "8080",
        "-fa", "1"
    ]

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def vectorstore_path(self) -> str:
        path = os.path.join(self.BASE_DIR, "embeddings")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def pdf_path(self) -> str:
        path = os.path.join(self.BASE_DIR, "pdfs")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def static_path(self) -> str:
        return os.path.join(self.BASE_DIR, "static")

settings = Settings()