import uvicorn
import os
import asyncio
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

# Imports do projeto
from app.api.routes import router
from app.dac.routes import dac_router
from app.core.config import settings
from app.core.database import Base, engine
from app.utils.logger import logger, setup_logging
from app.api import models
from app.dac import models as dac_models  # registra tabelas DAC no metadata

# Inicialização do Banco
try:
    models.Base.metadata.create_all(bind=engine)
    print("✅ Banco de dados sincronizado.")
except Exception as e:
    print(f"❌ Erro ao sincronizar banco: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 API Backend Iniciando...")
    yield
    logger.info("🛑 Desligando API...")

app = FastAPI(title="UCDB IA API", lifespan=lifespan)

# Middleware de Sessão (Necessário para algumas funções do FastAPI)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Configuração de CORS robusta
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Temporário para debug total
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError

# Captura de erros de validação (422) para debug
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"❌ ERRO DE VALIDAÇÃO (422) DETECTADO:\n{exc.errors()}")
    print(f"Dados recebidos: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# Captura de Erros Globais (Para sabermos por que dá Erro 500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    print(f"🔥 ERRO INTERNO DETECTADO:\n{error_trace}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "trace": error_trace}
    )

# Montagem das rotas
app.include_router(router)
app.include_router(dac_router)

# Servir arquivos estáticos (PDFs e fotos)
os.makedirs(settings.static_path, exist_ok=True)
os.makedirs(settings.pdf_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
app.mount("/pdfs", StaticFiles(directory=settings.pdf_path), name="pdfs")

if __name__ == "__main__":
    print("🚀 Servidor iniciando em http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
