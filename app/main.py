from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.api.routes import router
from app.utils.logger import setup_logging, logger
from app.core.config import settings
import os, socket, subprocess, time
from contextlib import asynccontextmanager

# --- IMPORTAÇÕES DO BANCO DE DADOS (NOVO) ---
from app.core.database import engine, Base
from app.api import models 

# --- CRIAÇÃO DAS TABELAS (NOVO) ---
# Isso cria o arquivo ucdb_ia.db com as tabelas User, Conversation, Message, etc.
models.Base.metadata.create_all(bind=engine)

_procs = []

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_service(name, port, cmd):
    if check_port(port):
        logger.info(f"✅ {name} online na porta {port}.")
        return
    
    logger.warning(f"⚠️ {name} offline. Tentando iniciar automaticamente...")
    try:
        # Ajuste para rodar em background sem travar e sem pedir input
        p = subprocess.Popen(cmd, cwd=settings.MODELS_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _procs.append(p)
        time.sleep(5) # Espera um pouco mais para o modelo carregar (VRAM)
        if check_port(port): 
            logger.success(f"🚀 {name} iniciado!")
        else:
            logger.error(f"❌ {name} falhou ao iniciar na porta {port}. Verifique os logs do sistema.")
    except Exception as e:
        logger.error(f"Erro ao iniciar {name}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 Iniciando UCDB-IA...")
    
    # Inicia Serviços Automaticamente se estiverem offline
    start_service("Embedding Server", 8081, settings.CMD_EMBEDDING)
    start_service("LLM Server", 8080, settings.CMD_LLM)
    
    yield
    logger.info("🛑 Encerrando...")
    for p in _procs: p.terminate()

app = FastAPI(title="UCDB Chat", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
    expose_headers=["*"]
)

app.include_router(router)

# Configuração de Arquivos Estáticos e PDFs
os.makedirs(settings.static_path, exist_ok=True)
os.makedirs(settings.pdf_path, exist_ok=True)

# Monta as rotas para servir os arquivos
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
app.mount("/pdfs", StaticFiles(directory=settings.pdf_path), name="pdfs")

if __name__ == "__main__":
    import uvicorn
    # A porta 8000 é onde o backend (e o banco) ficam disponíveis
    uvicorn.run(app, host="0.0.0.0", port=8000)