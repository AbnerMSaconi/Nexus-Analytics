import uvicorn
import os
import socket
import subprocess
import time
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from app.api.routes import router
from app.core.config import settings
from app.utils.logger import logger, setup_logging
from app.core.rag import atualizar_base_de_conhecimento

_processos_locais = []

def garantir_servico(nome: str, porta: int, comando: list):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", porta)) == 0:
            logger.info(f"✅ {nome} Online na porta {porta}.")
            return

    logger.warning(f"⚙️ Iniciando {nome}...")
    try:
        if not os.path.exists(settings.MODELS_DIR): return
        proc = subprocess.Popen(comando, cwd=settings.MODELS_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _processos_locais.append(proc)
        time.sleep(3) # Tempo técnico de boot
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar {nome}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 Servidor Iniciando...")
    
    # 1. Sobe Modelos
    garantir_servico("Embeddings", 8081, settings.CMD_EMBEDDING)
    garantir_servico("LLM", 8080, settings.CMD_LLM)

    # 2. Atualiza Conhecimento (Thread separada para não travar boot)
    asyncio.create_task(asyncio.to_thread(atualizar_base_de_conhecimento))
    
    yield
    
    logger.info("🛑 Desligando...")
    for proc in _processos_locais: proc.terminate()

app = FastAPI(title="UCDB IA", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(router)
os.makedirs(settings.static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
app.mount("/", StaticFiles(directory=settings.static_path, html=True), name="root")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)