# app/api/routes.py
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

# Limpa artefatos que o modelo possa gerar
def _limpar_resposta(texto: str) -> str:
    # Remove tags ChatML e outros artefatos
    texto = re.sub(r'<\|im_start\|>.*?(\n|$)', '', texto) # Remove cabeçalhos im_start
    texto = re.sub(r'<\|im_end\|>', '', texto)           # Remove im_end
    # Remove rótulos comuns
    texto = re.sub(r'^(Assitente:|Assistant:|Resposta:)\s*', '', texto, flags=re.IGNORECASE | re.MULTILINE)
    return texto.strip()

def _initialize_rag():
    global _vectorstore, _rag_chain, _initialized
    if _initialized: return True
    try:
        from app.core.rag import criar_vectorstore, criar_rag_chain
        logger.info("🚀 Inicializando RAG...")
        _vectorstore = criar_vectorstore()
        if _vectorstore:
            _rag_chain = criar_rag_chain(_vectorstore)
            logger.success("✅ RAG Online!")
            _initialized = True
            return True
        logger.warning("⚠️ RAG vazio (sem PDFs).")
        return False
    except Exception as e:
        logger.error(f"❌ Erro RAG: {e}")
        return False

def get_rag_chain():
    _initialize_rag()
    return _rag_chain

@router.get("/")
async def index():
    return FileResponse(os.path.join(settings.static_path, "index.html"))

@router.get("/knowledge-areas")
async def get_knowledge_areas():
    _initialize_rag()
    try:
        with open(os.path.join(settings.vectorstore_path, "manifest.json"), "r") as f:
            data = json.load(f)
            return {"areas": sorted(list(set(data.values())))}
    except: return {"areas": []}

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    if not body.message.strip(): return StreamingResponse(iter([]))
    rag_chain = get_rag_chain()
    if not rag_chain: return StreamingResponse(iter(['data: {"type": "error", "content": "Sistema iniciando..."}\n\n']))

    async def event_stream():
        try:
            # Gestão de Sessão
            session_id = request.cookies.get("session_id") or str(uuid.uuid4())
            if not hasattr(request.app, 'chat_memory'): request.app.chat_memory = {}
            history = request.app.chat_memory.setdefault(session_id, [])
            
            # Formata histórico para LangChain (apenas pares user/ai)
            tuples = [(h["content"], history[i+1]["content"]) for i, h in enumerate(history[:-1]) if h["role"] == "user" and i+1 < len(history)]

            def sse(d): return f"data: {json.dumps(d)}\n\n"
            yield sse({"type": "start"})

            # Invoca a IA
            res = await asyncio.to_thread(rag_chain.invoke, {"question": body.message, "chat_history": tuples[-6:]})
            
            raw_answer = res.get("answer", "")
            final_text = _limpar_resposta(raw_answer)
            if not final_text: final_text = "O documento não contém informações sobre isso."

            # ENVIA CARACTERE POR CARACTERE (Evita Loop)
            for char in final_text:
                yield sse({"type": "chunk", "content": char})
                await asyncio.sleep(0.001) # Delay técnico
            
            # Envia Fontes
            docs = res.get("source_documents", [])
            if docs:
                sources = []
                seen = set()
                for d in docs:
                    src = d.metadata.get("source", "Doc")
                    # Simplifica caminho para exibição
                    if "pdfs/" in src: src = src.split("pdfs/")[-1]
                    elif "/" in src: src = os.path.basename(src)
                    
                    pg = str(d.metadata.get("page", 0) + 1)
                    key = f"{src}|{pg}"
                    if key not in seen:
                        sources.append(key)
                        seen.add(key)
                yield sse({"type": "sources", "content": sources})

            # Atualiza Memória
            history.extend([{"role": "user", "content": body.message}, {"role": "ai", "content": final_text}])
            request.app.chat_memory[session_id] = history[-12:] # Mantém últimas 6 interações
            
            yield sse({"type": "complete"})

        except Exception as e:
            logger.error(f"Erro Stream: {e}")
            yield sse({"type": "error", "content": "Erro ao processar."})

    resp = StreamingResponse(event_stream(), media_type="text/event-stream")
    if not request.cookies.get("session_id"):
        resp.set_cookie("session_id", str(uuid.uuid4()))
    return resp