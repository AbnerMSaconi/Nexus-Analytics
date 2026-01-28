# app/api/routes.py - Versão Restaurada com Memória e Links

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, FileResponse
from app.api.schemas import ChatRequest
from app.core.config import settings
from app.utils.logger import logger
import os
import json
import uuid
import asyncio
import re

router = APIRouter()

_vectorstore = None
_rag_chain = None
_initialized = False
_initialization_failed = False

def _limpar_resposta_llm(texto: str) -> str:
    if not texto: return ""
    texto_limpo = re.sub(r'^[^\w\s]*\s*$', '', texto, flags=re.MULTILINE)
    texto_limpo = re.sub(r'\n{3,}', '\n\n', texto_limpo)
    return texto_limpo.strip()

def _remover_duplicacao(texto: str, logger) -> str:
    texto = texto.strip()
    tamanho = len(texto)
    if tamanho > 50 and tamanho % 2 == 0:
        meio = tamanho // 2
        primeira_metade = texto[:meio].strip()
        segunda_metade = texto[meio:].strip()
        if primeira_metade == segunda_metade and primeira_metade:
            return primeira_metade
    return texto

def _initialize_rag():
    global _vectorstore, _rag_chain, _initialized, _initialization_failed
    if _initialized or _initialization_failed:
        return _initialized
    try:
        from app.core.rag import criar_vectorstore, criar_rag_chain
        logger.info("🚀 Inicializando sistema RAG Único...")
        _vectorstore = criar_vectorstore()
        if not _vectorstore:
            logger.warning("⚠️ Nenhum documento encontrado.")
        else:
            _rag_chain = criar_rag_chain(_vectorstore)
            logger.success("✅ Sistema RAG inicializado com sucesso!")
        _initialized = True
        return True
    except Exception as e:
        logger.critical(f"❌ Falha crítica ao inicializar RAG: {e}")
        _initialization_failed = True
        return False

def get_rag_chain():
    if not _initialize_rag(): return None
    return _rag_chain

@router.get("/")
async def index():
    return FileResponse(os.path.join(settings.static_path, "index.html"))

@router.get("/knowledge-areas")
async def get_knowledge_areas():
    """Retorna a lista de ASSUNTOS identificados (não nomes de arquivos)."""
    _initialize_rag() # Garante que está carregado
    manifest_path = os.path.join(settings.vectorstore_path, "manifest.json")
    if not os.path.exists(manifest_path): return {"areas": []}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            # Retorna apenas os valores únicos (Assuntos) ordenados
            return {"areas": sorted(list(set(manifest_data.values())))}
    except Exception:
        return {"areas": []}

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    if not body.message.strip():
        return StreamingResponse(iter(['data: {"type": "error", "content": "Vazio"}\n\n']), media_type="text/event-stream")

    rag_chain = get_rag_chain()
    if not rag_chain:
        return StreamingResponse(iter(['data: {"type": "error", "content": "RAG offline"}\n\n']), media_type="text/event-stream")

    async def event_stream():
        try:
            # Recupera histórico da memória da aplicação usando Cookie
            session_id = request.cookies.get("session_id") or str(uuid.uuid4())
            # Usa request.app.state ou um dicionário global simples para persistência em memória
            if not hasattr(request.app, 'chat_history_memory'):
                request.app.chat_history_memory = {}
            
            history = request.app.chat_history_memory
            session_hist = history.setdefault(session_id, [])
            
            # Converte para tuplas (User, AI) para o LangChain
            chat_history_tuples = []
            for i in range(0, len(session_hist), 2):
                if i + 1 < len(session_hist):
                    chat_history_tuples.append((session_hist[i]["content"], session_hist[i+1]["content"]))

            def format_sse(data: dict) -> str: return f"data: {json.dumps(data)}\n\n"

            yield format_sse({"type": "start"})
            
            # Invocação do RAG
            result = await asyncio.to_thread(
                rag_chain.invoke, {"question": body.message, "chat_history": chat_history_tuples}
            )

            raw_answer = result.get("answer", "").strip()
            resposta_final = _remover_duplicacao(_limpar_resposta_llm(raw_answer), logger)

            if not resposta_final: resposta_final = "Não encontrei informações suficientes."

            # Processamento de Fontes para Links
            source_docs = result.get("source_documents", [])
            fontes = []
            if source_docs:
                unique_sources = {}
                for doc in source_docs:
                    # source agora pode ser "pasta/arquivo.pdf" ou "arquivo.pdf"
                    rel_path = doc.metadata.get("source", "Desconhecido")
                    filename = os.path.basename(rel_path)
                    
                    if rel_path not in unique_sources: unique_sources[rel_path] = set()
                    unique_sources[rel_path].add(str(doc.metadata.get("page", 0) + 1))
                
                # Formata para enviar ao frontend: "CAMINHO|PÁGINAS"
                # O frontend vai quebrar isso para criar o link
                fontes = [f"{path}|{', '.join(sorted(pages))}" for path, pages in unique_sources.items()]

            # Atualiza histórico
            session_hist.extend([
                {"role": "user", "content": body.message},
                {"role": "ai", "content": resposta_final}
            ])
            # Mantém apenas as últimas 6 trocas para não estourar o contexto
            history[session_id] = session_hist[-12:]

            # Streaming da resposta
            buffer = ""
            for char in resposta_final:
                buffer += char
                yield format_sse({"type": "chunk", "content": buffer})
                await asyncio.sleep(0.002)

            if fontes:
                yield format_sse({"type": "sources", "content": fontes})
            
            yield format_sse({"type": "complete"})
        
        except Exception as e:
            logger.error(f"Erro: {e}")
            yield format_sse({"type": "error", "content": str(e)})

    response = StreamingResponse(event_stream(), media_type="text/event-stream")
    if not request.cookies.get("session_id"):
        response.set_cookie("session_id", str(uuid.uuid4()), httponly=True)
    return response