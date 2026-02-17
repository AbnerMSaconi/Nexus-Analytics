# app/main.py - Ponto de Entrada
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.api.routes import router
from app.utils.logger import setup_logging, logger
from app.core.config import settings
import os
from contextlib import asynccontextmanager
from app.core.rag import atualizar_base_de_conhecimento
from app.core.database import Base, engine # Importar Base e engine para criar tabelas

# Criar tabelas no banco de dados se não existirem
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 API Backend Iniciando...")
    
    # Inicia a indexação em background sem travar o boot
    import asyncio
    asyncio.create_task(asyncio.to_thread(atualizar_base_de_conhecimento))
    
    yield
    logger.info("🛑 Desligando API...")

app = FastAPI(title="UCDB Chat", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], # Em produção, restrinja isso!
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

app.include_router(router)

# --- AQUI ESTÁ A CORREÇÃO ---
# Garante que as pastas existem antes de montar
os.makedirs(settings.static_path, exist_ok=True)
os.makedirs(settings.pdf_path, exist_ok=True)

# Monta a rota /pdfs para servir arquivos REAIS do disco
app.mount("/pdfs", StaticFiles(directory=settings.pdf_path), name="pdfs")
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)