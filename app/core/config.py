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

    # RAG
    CHUNK_SIZE: int = 1200      # Tamanho ideal. Cabe um Artigo inteiro com uns 10 incisos.
    CHUNK_OVERLAP: int = 300    # Excelente "cola". 300 caracteres garantem que a palavra não corte no meio.
    RETRIEVAL_K: int = 8        # Puxa os 8 melhores pedaços. 

    # CAMINHOS
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Garanta que este caminho é onde você salvou o arquivo .gguf
    MODELS_DIR: str = os.path.expanduser("~/.cache/llama.cpp")
    
    # MODELO DE EMBEDDING (Mantém o Qwen, é ótimo)
    CMD_EMBEDDING: list = [
        "llama-server", "-m", "Qwen_Qwen3-Embedding-0.6B-GGUF_Qwen3-Embedding-0.6B-Q8_0.gguf",
        "--embedding", "--port", "8081"
    ]

    # NOVO MODELO LLM (Hermes 3 - Llama 3.1)
    # Substitua 'Hermes-3-Llama-3.1-8B.Q4_K_M.gguf' pelo nome exato do arquivo que você baixou
    CMD_LLM: list = [
        "llama-server", 
        "-m", "NousResearch_Hermes-3-Llama-3.1-8B-GGUF_Hermes-3-Llama-3.1-8B.Q4_K_M.gguf", 
        "--port", "8080", 
        "-fa", "1",       # Flash Attention (essencial para Llama 3)
        "-c", "16384",     # Contexto
        "-ngl", "99"      # GPU Offload máximo
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