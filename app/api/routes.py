"""
UCDB-IA | Roteamento de Produção e Agentes
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from app.api.schemas import ChatRequest
from app.utils.logger import logger
from app.core.config import settings
import json, asyncio, uuid, os, html
from urllib.parse import quote

router = APIRouter()

# --- Cache de Motor ---
_rag_chain = None

def _get_engine():
    global _rag_chain
    if _rag_chain: return _rag_chain
    try:
        from app.core.rag import criar_vectorstore, criar_rag_chain
        vs = criar_vectorstore()
        if vs:
            _rag_chain = criar_rag_chain(vs)
            return _rag_chain
    except: pass
    return None

@router.get("/")
async def index():
    return FileResponse(os.path.join(settings.static_path, "index.html"))

@router.get("/knowledge-areas")
async def listar_materiais_organizados():
    """Retorna materiais agrupados por blocos disciplinares para a Sidebar."""
    vs_path = settings.vectorstore_path
    manifesto_path = os.path.join(vs_path, "manifest.json")
    
    if not os.path.exists(manifesto_path):
        return {"categorias": {}}
    
    try:
        with open(manifesto_path, "r", encoding="utf-8") as f:
            manifesto = json.load(f)
        
        agrupado = {}
        for info in manifesto.values():
            cat = info.get("categoria", "Material Geral")
            tit = info.get("titulo", "Sem Título")
            if cat not in agrupado: agrupado[cat] = []
            if tit not in agrupado[cat]: agrupado[cat].append(tit)
        
        return {"categorias": agrupado}
    except Exception as e:
        logger.error(f"Erro ao processar categorias: {e}")
        return {"categorias": {}}

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    async def event_stream():
        def sse(d: dict) -> str: return f"data: {json.dumps(d)}\n\n"
        try:
            yield sse({"type": "start"})
            await asyncio.sleep(0.1)

            engine = _get_engine()
            if not engine:
                yield sse({"type": "error", "content": "Sistema em manutenção."})
                return

            res = await asyncio.to_thread(engine.invoke, {"question": body.message, "chat_history": []})
            
            # Prepara Referências bibliográficas (Sidebar Direita)
            fontes = []
            docs = res.get("source_documents", [])
            for i, doc in enumerate(docs):
                nome = os.path.basename(doc.metadata.get("source", "PDF"))
                pag = int(doc.metadata.get("page", 0)) + 1
                fontes.append({
                    "source": f"{nome} (Pág. {pag})",
                    "content": html.escape(doc.page_content[:400])
                })
            
            if fontes:
                yield sse({"type": "source_chunks", "content": fontes})

            yield sse({"type": "chunk", "content": res.get("answer", "")})
            yield sse({"type": "complete"})

        except Exception as e:
            logger.error(f"Erro Stream: {e}")
            yield sse({"type": "error", "content": "Falha no processamento."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")