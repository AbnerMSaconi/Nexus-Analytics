from pydantic_settings import SettingsConfigDict, BaseSettings
from pydantic import AnyHttpUrl
import os
import secrets

class Settings(BaseSettings):
    # API
    APP_NAME: str = "UCDB Chat"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "chave_super_secreta_padrao_para_desenvolvimento_troque_em_prod")

    # SERVIÇOS
    LLM_BASE_URL: AnyHttpUrl = "http://localhost:8080/v1"
    EMBEDDING_API_URL: AnyHttpUrl = "http://localhost:8081/embedding"
    
    # PARAMETROS DO MODELO (Hermes 3)
    MAX_TOKENS: int = 8192      
    TEMPERATURE: float = 0.0   # Hermes é criativo, 0.3 segura alucinações
    TOP_P: float = 0.90
    REPETITION_PENALTY: float = 1.05 # Llama 3.1 repete menos, penalidade leve

    # RAG - Otimizado para modelos locais (Qwen/Llama)
    CHUNK_SIZE: int = 600      # Reduzido de 1200 para 600 para evitar erro de contexto
    CHUNK_OVERLAP: int = 100    # Reduzido de 300 para 100
    RETRIEVAL_K: int = 5        # Reduzido de 8 para 5 para economizar contexto no chat

    # CAMINHOS
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Garanta que este caminho é onde você salvou o arquivo .gguf
    MODELS_DIR: str = os.getenv("MODELS_DIR", os.path.expanduser("~/.cache/llama.cpp"))
    
    # MODELO DE EMBEDDING (Qwen 3B/4B)
    CMD_EMBEDDING: list = [
        "llama-server", "-m", "qwen2.5-3b-instruct-q4_k_m.gguf",
        "--embedding", "--port", "8081"
    ]

    # PARÂMETROS DE ESCALABILIDADE (Ajustados para Hardware Local)
    # ATENÇÃO: Cada slot (-np) reserva memória (KV Cache). 
    # Para 32k de contexto, cada slot consome ~7GB de RAM/VRAM.
    # Valores seguros para máquinas locais: -np 2 a 4.
    LLM_PARALLEL: int = os.getenv("LLM_PARALLEL", 4) 
    
    # MODELO LLM (Qwen 3B/4B Instruct)
    @property
    def CMD_LLM(self) -> list:
        return [
            "llama-server", 
            "-m", "qwen2.5-3b-instruct-q4_k_m.gguf", 
            "--port", "8080", 
            "-fa", "1",           # Flash Attention
            "-c", "8192",         # Contexto reduzido de 32k para 8k (Estabilidade)
            "-ngl", "99",         # Máximo de camadas na GPU
            "-np", str(self.LLM_PARALLEL), # Slots paralelos seguros
            "--cont-batching",    # Continuous Batching
            "-cb"
        ]
    
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