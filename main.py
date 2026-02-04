import uvicorn
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

# --- AQUI ESTAVA O ERRO ---
# Atualizamos a importação para usar a função correta definida no routes.py
from app.api.routes import router, initialize_rag_system
from app.core.config import settings
from app.utils.logger import logger, setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🚀 Iniciando Servidor UCDB-IA...")
    
    # Chama a função correta de inicialização
    await initialize_rag_system()
    
    yield
    logger.info("🛑 Servidor desligando...")

app = FastAPI(title="UCDB Chat", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Configuração de arquivos estáticos
os.makedirs(settings.static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
app.mount("/", StaticFiles(directory=settings.static_path, html=True), name="root")

if __name__ == "__main__":
    # Rodando em 0.0.0.0 para acesso externo (Servidor Dedicado)
    uvicorn.run(app, host="0.0.0.0", port=8000)