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

# IMPORTANTE: Importando da nova estrutura do rag.py
from app.core.rag import carregar_indices, get_rag_chain

router = APIRouter()

_initialized = False

def _limpar_resposta(texto: str) -> str:
    # Mantém sua lógica de limpeza, vital para modelos ChatML/Hermes
    texto = re.sub(r'<\|im_start\|>.*?(\n|$)', '', texto)
    texto = re.sub(r'<\|im_end\|>', '', texto)
    texto = re.sub(r'^(Assitente:|Assistant:|Resposta:)\s*', '', texto, flags=re.IGNORECASE | re.MULTILINE)
    return texto

async def initialize_rag_system():
    global _initialized
    if _initialized: return
    
    logger.info("🚀 Inicializando Sistema de Especialistas (RAG)...")
    # Agora carrega o dicionário de índices (Engenharia, Direito, etc)
    indices = await asyncio.to_thread(carregar_indices)
    
    if indices:
        logger.success(f"✅ {len(indices)} áreas de conhecimento carregadas!")
        _initialized = True
    else:
        logger.warning("⚠️ Nenhum índice encontrado em storage_indexes/.")

@router.get("/")
async def index():
    return FileResponse(os.path.join(settings.static_path, "index.html"))

@router.get("/knowledge-areas")
async def get_knowledge_areas():
    # Retorna as pastas encontradas em storage_indexes
    try:
        base_path = "storage_indexes"
        if not os.path.exists(base_path): return {"areas": []}
        
        areas = [d.replace("index_", "").capitalize() for d in os.listdir(base_path) if d.startswith("index_")]
        return {"areas": sorted(areas)}
    except: return {"areas": []}

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    if not body.message.strip(): return StreamingResponse(iter([]))
    
    # 1. Recupera a chain correta para a área solicitada
    area_key = body.area.lower() if body.area else "institucional"
    try:
        # Aqui conectamos a escolha do usuário com o índice específico
        chain = get_rag_chain(area_key)
    except ValueError:
        # Fallback se a área não existir
        chain = get_rag_chain("institucional")

    async def event_stream():
        try:
            session_id = request.cookies.get("session_id") or str(uuid.uuid4())
            if not hasattr(request.app, 'chat_memory'): request.app.chat_memory = {}
            history = request.app.chat_memory.setdefault(session_id, [])
            
            # Converte histórico para tuplas (User, AI)
            chat_history = [(h["content"], history[i+1]["content"]) for i, h in enumerate(history[:-1]) if h["role"] == "user" and i+1 < len(history)]

            def sse(d): return f"data: {json.dumps(d)}\n\n"
            yield sse({"type": "start"})

            # 2. STREAMING REAL (Corrigido para o seu Frontend)
            # Usamos .astream para não bloquear o servidor enquanto gera
            full_answer = ""
            source_documents = []

            # O input do invoke/stream depende de como o chain foi criado no rag.py.
            # Geralmente ConversationalRetrievalChain aceita "question" e "chat_history"
            async for chunk in chain.astream({"question": body.message, "chat_history": chat_history}):
                
                # Captura trechos da resposta (Answer)
                if "answer" in chunk:
                    token = chunk["answer"]
                    token = _limpar_resposta(token) # Limpeza em tempo real
                    if token:
                        full_answer += token
                        # Envia no formato exato que o script.js espera
                        yield sse({"type": "chunk", "content": token})
                
                # Captura documentos fonte (geralmente vem no final ou num chunk específico)
                if "source_documents" in chunk:
                    source_documents = chunk["source_documents"]

            # 3. Processamento de Fontes (Mantendo sua lógica de visualização)
            if source_documents:
                sources = []
                seen = set()
                for d in source_documents:
                    # Tenta pegar metadados, com fallbacks
                    src = d.metadata.get("source", "Doc")
                    page = str(d.metadata.get("page", 0) + 1)
                    
                    # Limpa o caminho do arquivo para ficar bonito no frontend
                    if "pdfs/" in src: src = src.split("pdfs/")[-1]
                    elif "/" in src: src = os.path.basename(src)
                    
                    key = f"{src}|{page}"
                    if key not in seen:
                        sources.append(key)
                        seen.add(key)
                
                yield sse({"type": "sources", "content": sources})

            # Atualiza memória
            history.extend([{"role": "user", "content": body.message}, {"role": "ai", "content": full_answer}])
            request.app.chat_memory[session_id] = history[-10:] # Mantém contexto curto e eficiente
            
            yield sse({"type": "complete"})

        except Exception as e:
            logger.error(f"Erro Stream: {e}")
            yield sse({"type": "error", "content": "Desculpe, tive um erro ao processar sua solicitação."})

    resp = StreamingResponse(event_stream(), media_type="text/event-stream")
    if not request.cookies.get("session_id"):
        resp.set_cookie("session_id", str(uuid.uuid4()))
    return resp