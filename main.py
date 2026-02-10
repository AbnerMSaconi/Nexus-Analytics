import uvicorn
import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router
from app.core.config import settings
from app.core.database import Base, engine
from app.utils.logger import logger, setup_logging
from app.core.rag import atualizar_base_de_conhecimento

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("🌐 API Backend Iniciando...")
    # Aqui entraria a lógica de iniciar LLM local, se necessário
    asyncio.create_task(asyncio.to_thread(atualizar_base_de_conhecimento))
    yield
    logger.info("🛑 Desligando API...")

app = FastAPI(title="UCDB IA API", lifespan=lifespan)

# CORS Permitindo que o React (localhost:5173) acesse o Python (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)