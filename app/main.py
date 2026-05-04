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

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 Iniciando UCDB-IA (Backend Service)...")
    
    # Em Docker/vLLM, os serviços de inferência são gerenciados externamente
    llm_url = str(settings.LLM_BASE_URL)
    emb_url = str(settings.EMBEDDING_API_URL)
    
    logger.info(f"🔗 Conectado ao LLM Server: {llm_url}")
    logger.info(f"🔗 Conectado ao Embedding Server: {emb_url}")
    
    yield
    logger.info("🛑 Encerrando backend...")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

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