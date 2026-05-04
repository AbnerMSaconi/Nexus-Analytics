from pydantic_settings import SettingsConfigDict, BaseSettings
from pydantic import AnyHttpUrl
import os

class Settings(BaseSettings):
    # API
    APP_NAME: str = "UCDB-IA Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "chave_super_secreta_padrao_para_desenvolvimento")

    # SERVIÇOS (vLLM & Llama.cpp)
    LLM_BASE_URL: AnyHttpUrl = "http://localhost:8080/v1"
    EMBEDDING_API_URL: AnyHttpUrl = "http://localhost:8081/embedding"
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen2.5-3b-instruct")
    
    # PARÂMETROS DO MODELO
    MAX_TOKENS: int = 8192      
    TEMPERATURE: float = 0.0
    TOP_P: float = 0.90
    REPETITION_PENALTY: float = 1.05

    # RAG - OTIMIZADO (Sliding Window & Higher Context)
    CHUNK_SIZE: int = 700      # Reduzido para ser mais específico
    CHUNK_OVERLAP: int = 300    # Aumentado para não perder contexto entre chunks
    RETRIEVAL_K: int = 15       # Aumentado para buscar mais trechos candidatos

    # CAMINHOS
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    MODELS_DIR: str = os.getenv("MODELS_DIR", os.path.expanduser("~/.cache/llama.cpp"))
    
    # PARÂMETROS DE ESCALABILIDADE
    LLM_PARALLEL: int = os.getenv("LLM_PARALLEL", 4) # vLLM lida com concorrência nativamente
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

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
