import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from app.api.routes import router
from app.dac.routes import dac_router
from app.utils.logger import setup_logging, logger
from app.core.config import settings
import os
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.api import models
from app.dac import models as dac_models  # registra tabelas DAC no metadata

models.Base.metadata.create_all(bind=engine)

_procs = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 Iniciando Nexus (Backend Service)...")
    
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

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    print(f"🔴 HTTP {exc.status_code} em {request.method} {request.url.path}: {exc.detail}")
    headers = getattr(exc, 'headers', None)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"❌ ERRO DE VALIDAÇÃO (422) em {request.method} {request.url.path}:\n{exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    print(f"🔥 ERRO INTERNO em {request.method} {request.url.path}:\n{error_trace}")
    return JSONResponse(status_code=500, content={"detail": str(exc), "trace": error_trace})

app.include_router(router)
app.include_router(dac_router)

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