"""
UCDB-IA | Roteamento com Seleção Dinâmica de Base de Conhecimento
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, FileResponse
from app.api.schemas import ChatRequest
from app.utils.logger import logger
from app.core.config import settings
from app.core.rag import carregar_motor_especifico, inicializar_bases_de_conhecimento
import json, asyncio, os, html

router = APIRouter()

# Cache de motores carregados para não abrir o disco a toda hora
_motores_cache = {}

@router.get("/")
async def index():
    return FileResponse(os.path.join(settings.static_path, "index.html"))

@router.get("/knowledge-areas")
async def listar_areas_reais():
    """
    Lista as pastas reais dentro de /pdfs para montar o menu lateral.
    """
    if not os.path.exists(settings.pdf_path):
        return {"categorias": {}}
    
    # Lê as pastas físicas
    areas = [d for d in os.listdir(settings.pdf_path) if os.path.isdir(os.path.join(settings.pdf_path, d))]
    
    estrutura = {}
    for area in areas:
        # Lista os arquivos dentro de cada pasta de área
        arquivos = os.listdir(os.path.join(settings.pdf_path, area))
        estrutura[area] = [f for f in arquivos if f.endswith(".pdf")]
        
    return {"categorias": estrutura}

def _identificar_area_no_texto(mensagem: str, areas_disponiveis: list):
    """Tenta descobrir qual especialista o usuário quer baseado na mensagem."""
    mensagem = mensagem.lower()
    for area in areas_disponiveis:
        if area.lower() in mensagem:
            return area
    return None

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    # Recupera ou inicia o estado da sessão
    session = request.session
    area_atual = session.get("area_atual", "Geral") # Padrão se não achar nada

    # 1. Tenta detectar troca de especialista na mensagem (Ex: "Olá Especialista em Direito")
    # Lista áreas reais disponíveis no disco
    areas_reais = [d for d in os.listdir(settings.pdf_path) if os.path.isdir(os.path.join(settings.pdf_path, d))]
    nova_area = _identificar_area_no_texto(body.message, areas_reais)
    
    if nova_area:
        area_atual = nova_area
        session["area_atual"] = area_atual # Salva na sessão do usuário
    
    logger.info(f"📢 Respondendo usando base de: {area_atual}")

    async def event_stream():
        def sse(d): return f"data: {json.dumps(d)}\n\n"
        try:
            yield sse({"type": "start"})
            
            # Carrega o motor específico da área (com cache)
            if area_atual not in _motores_cache:
                motor = carregar_motor_especifico(area_atual)
                if motor:
                    _motores_cache[area_atual] = motor
                else:
                    # Se não tiver motor para a área (ex: primeira vez ou pasta vazia)
                    yield sse({"type": "chunk", "content": f"Ainda não tenho materiais indexados para a área de **{area_atual}**. Por favor, adicione PDFs na pasta correspondente."})
                    yield sse({"type": "complete"})
                    return
            
            engine = _motores_cache[area_atual]
            
            # Executa a IA em Thread separada
            res = await asyncio.to_thread(engine.invoke, {"question": body.message, "chat_history": []})
            
            # Processa fontes
            fontes = []
            for doc in res.get("source_documents", []):
                fontes.append({
                    "source": os.path.basename(doc.metadata.get("source", "Doc")),
                    "content": html.escape(doc.page_content[:300])
                })
            
            if fontes: yield sse({"type": "source_chunks", "content": fontes})
            yield sse({"type": "chunk", "content": res.get("answer", "")})
            yield sse({"type": "complete"})

        except Exception as e:
            logger.error(f"Erro: {e}")
            yield sse({"type": "error", "content": "Erro ao processar sua dúvida."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")