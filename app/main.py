from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os

# IMPORTANTE: Importando a função correta definida no routes.py atualizado
from app.api.routes import router, initialize_rag_system
from app.core.config import settings
from app.utils.logger import logger, setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🚀 Iniciando Servidor UCDB-IA...")
    
    # Inicializa o sistema de RAG (carrega índices FAISS)
    await initialize_rag_system()
    
    yield
    logger.info("🛑 Servidor desligando...")

app = FastAPI(title="UCDB Chat", lifespan=lifespan)

# Configurações de Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas e Arquivos Estáticos
app.include_router(router, prefix="/api") # Prefixo opcional, ajustado conforme seu frontend
# Se o seu frontend chama direto /chat sem /api, use: app.include_router(router)
# Pelo erro anterior, vou assumir sem prefixo para compatibilidade total:
app.include_router(router)

os.makedirs(settings.static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
# Monta a raiz para servir o index.html
app.mount("/", StaticFiles(directory=settings.static_path, html=True), name="root")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)