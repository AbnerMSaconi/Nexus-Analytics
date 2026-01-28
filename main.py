from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from starlette.middleware.sessions import SessionMiddleware
from app.utils.logger import setup_logging, logger
from app.core.config import settings
import os
from app.core.rag import inicializar_bases_de_conhecimento
from contextlib import asynccontextmanager # <--- 1. Nova importação necessária

# 2. Definir a função lifespan (gerencia o ciclo de vida da aplicação)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Lógica de Startup (Início) ---
    logger.info("🌐 UCDB Chat iniciado!")
    
    # (A chamada incorreta para _get_engine() foi removida daqui)

    try:
        # Varre as pastas e cria os índices separados
        inicializar_bases_de_conhecimento()
    except Exception as e:
        logger.warning(f"⚠️ Erro na indexação inicial: {e}")
    
    logger.info(f"💡 Servidor rodando em http://localhost:8000")
    
    yield # O ponto onde a aplicação roda e atende requisições
    
    # --- Lógica de Shutdown (Desligamento) ---
    # Se precisar limpar recursos ao fechar o servidor, coloque aqui.
    logger.info("🛑 UCDB Chat finalizando...")

def create_app() -> FastAPI:
    setup_logging()
    
    # 3. Passar o parâmetro lifespan na criação do app
    app = FastAPI(title="UCDB Chat", lifespan=lifespan)

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    static_dir = settings.static_path
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    pdf_dir = settings.pdf_path
    os.makedirs(pdf_dir, exist_ok=True)
    app.mount("/pdfs", StaticFiles(directory=pdf_dir), name="pdfs")
    
    # (O bloco antigo @app.on_event("startup") foi removido)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)