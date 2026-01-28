from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from starlette.middleware.sessions import SessionMiddleware
from app.utils.logger import setup_logging, logger
from app.core.config import settings
import os
import socket
import subprocess
import time
from app.core.rag import inicializar_bases_de_conhecimento
from contextlib import asynccontextmanager

# Lista para armazenar processos iniciados e matá-los ao encerrar o app
_processos_locais = []

def verificar_porta(host: str, port: int) -> bool:
    """Retorna True se a porta estiver aberta (serviço rodando)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

def iniciar_servico_se_necessario(nome: str, porta: int, comando: list, pergunta: str):
    """Verifica a porta e, se fechada, pergunta ao usuário se deseja iniciar."""
    host = "127.0.0.1"
    if verificar_porta(host, porta):
        logger.info(f"✅ {nome} detectado na porta {porta}.")
        return

    logger.warning(f"⚠️ {nome} não detectado na porta {porta}.")
    
    # Loop simples para garantir resposta válida
    while True:
        try:
            resposta = input(f"👉 {pergunta} (s/n): ").lower().strip()
            if resposta in ['s', 'sim', 'y', 'yes']:
                logger.info(f"🚀 Iniciando {nome}...")
                
                # Inicia o processo no diretório configurado (~/.cache/llama.cpp)
                proc = subprocess.Popen(
                    comando,
                    cwd=settings.MODELS_DIR,
                    stdout=subprocess.DEVNULL, # Oculta logs do llama-server para não poluir
                    stderr=subprocess.DEVNULL  # Mude para subprocess.PIPE se quiser ver erros
                )
                _processos_locais.append(proc)
                
                # Aguarda um pouco para o servidor subir
                logger.info("⏳ Aguardando inicialização...")
                time.sleep(3) 
                
                if verificar_porta(host, porta):
                    logger.info(f"✅ {nome} iniciado com sucesso!")
                else:
                    logger.warning(f"⚠️ {nome} foi iniciado, mas a porta ainda não respondeu. Pode levar alguns segundos.")
                break
            elif resposta in ['n', 'nao', 'no']:
                logger.info(f"Mantis serviço {nome} desligado.")
                break
        except EOFError:
            # Caso esteja rodando em ambiente sem input (ex: docker background)
            break

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("🌐 UCDB Chat iniciado!")
    
    # 1. Verificar e oferecer inicialização do Embeddings (Porta 8081)
    iniciar_servico_se_necessario(
        nome="Modelo Embeddings (Qwen3)",
        porta=8081,
        comando=settings.CMD_EMBEDDING,
        pergunta="Modelo embeddings não iniciado. Deseja iniciar o Qwen3 Embeddings?"
    )

    # 2. Verificar e oferecer inicialização do LLM (Porta 8080)
    iniciar_servico_se_necessario(
        nome="Modelo LLM (GLM-4)",
        porta=8080,
        comando=settings.CMD_LLM,
        pergunta="Modelo LLM não iniciado. Deseja iniciar o GLM-4?"
    )

    try:
        # Varre as pastas e cria os índices separados
        inicializar_bases_de_conhecimento()
    except Exception as e:
        logger.warning(f"⚠️ Erro na indexação inicial: {e}")
    
    logger.info(f"💡 Servidor rodando em http://localhost:8000")
    
    yield # Servidor roda aqui
    
    # --- Shutdown ---
    logger.info("🛑 UCDB Chat finalizando...")
    if _processos_locais:
        logger.info("🔪 Encerrando modelos locais iniciados...")
        for proc in _processos_locais:
            proc.terminate()
            proc.wait()

def create_app() -> FastAPI:
    setup_logging()
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

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    # Importante: workers=1 para garantir que o input() funcione e não haja conflito de portas
    uvicorn.run(app, host="0.0.0.0", port=8000)