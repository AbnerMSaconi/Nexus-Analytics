from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, FileResponse
from app.api.schemas import ChatRequest
from app.core.config import settings
from app.utils.logger import logger
from app.core.rag import get_rag_chain, atualizar_base_de_conhecimento
from langchain_core.messages import HumanMessage, AIMessage
import os
import json
import uuid

router = APIRouter()

@router.on_event("startup")
async def startup_event():
    # Ingestão acontece no main.py, mas aqui garantimos pastas
    pass

@router.get("/")
async def index():
    return FileResponse(os.path.join(settings.static_path, "index.html"))

@router.get("/knowledge-areas")
async def get_knowledge_areas():
    try:
        base = settings.vectorstore_path
        if not os.path.exists(base): return {"areas": []}
        areas = [d.replace("index_", "").capitalize() for d in os.listdir(base) if d.startswith("index_")]
        return {"areas": sorted(areas)}
    except: return {"areas": []}

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    if not body.message.strip(): return StreamingResponse(iter([]))
    
    rag_chain = get_rag_chain(body.area)
    if not rag_chain: 
        return StreamingResponse(iter(['data: {"type": "error", "content": "Sistema iniciando ou índice vazio."}\n\n']))

    async def event_stream():
        try:
            session_id = request.cookies.get("session_id") or str(uuid.uuid4())
            if not hasattr(request.app, 'chat_memory'): request.app.chat_memory = {}
            history = request.app.chat_memory.setdefault(session_id, [])
            
            # Conversão para LCEL
            history_lc = []
            for msg in history[-6:]:
                if msg["role"] == "user": history_lc.append(HumanMessage(content=msg["content"]))
                else: history_lc.append(AIMessage(content=msg["content"]))

            def sse(d): return f"data: {json.dumps(d)}\n\n"
            yield sse({"type": "start"})

            full_answer = ""
            source_documents = []

            async for chunk in rag_chain.astream({
                "question": body.message,
                "chat_history": history_lc
            }):
                if "answer" in chunk and chunk["answer"]:
                    token = chunk["answer"]
                    full_answer += token
                    yield sse({"type": "chunk", "content": token})
                
                if "source_documents" in chunk:
                    source_documents = chunk["source_documents"]

            if source_documents:
                sources = []
                seen = set()
                for d in source_documents:
                    name = os.path.basename(d.metadata.get("source", "Doc"))
                    if name not in seen:
                        sources.append(name)
                        seen.add(name)
                yield sse({"type": "sources", "content": sources})

            history.extend([{"role": "user", "content": body.message}, {"role": "ai", "content": full_answer}])
            request.app.chat_memory[session_id] = history[-10:]
            yield sse({"type": "complete"})

        except Exception as e:
            logger.error(f"Erro Stream: {e}")
            yield sse({"type": "error", "content": "Erro no servidor."})

    resp = StreamingResponse(event_stream(), media_type="text/event-stream")
    if not request.cookies.get("session_id"):
        resp.set_cookie("session_id", str(uuid.uuid4()))
    return resp