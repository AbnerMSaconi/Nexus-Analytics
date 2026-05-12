import json
import csv
import io
from fastapi import APIRouter, Depends, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.llm import get_llm
from app.api.models import User
from app.dac.models import DacEscola, DacDadosEscolares
from app.dac.importer import importar_csv_bytes, carregar_serie_historica, get_progresso

dac_router = APIRouter(prefix="/dac", tags=["DAC - Educação MS"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _agregado_por_municipio_ano(db: Session, municipio: Optional[str], ano: Optional[int]) -> list[dict]:
    q = (
        db.query(
            DacEscola.municipio,
            DacDadosEscolares.ano,
            func.sum(DacDadosEscolares.total_matriculas).label("total_matriculas"),
            func.sum(DacDadosEscolares.aprovados).label("aprovados"),
            func.sum(DacDadosEscolares.reprovados).label("reprovados"),
            func.sum(DacDadosEscolares.abandono).label("abandono"),
            func.sum(DacDadosEscolares.transferidos).label("transferidos"),
            func.count(distinct(DacEscola.id)).label("total_escolas"),
        )
        .join(DacEscola, DacDadosEscolares.escola_id == DacEscola.id)
    )
    if municipio:
        q = q.filter(DacEscola.municipio == municipio)
    if ano:
        q = q.filter(DacDadosEscolares.ano == ano)

    q = q.group_by(DacEscola.municipio, DacDadosEscolares.ano).order_by(DacDadosEscolares.ano)

    resultado = []
    for row in q.all():
        base = (row.aprovados or 0) + (row.reprovados or 0) + (row.abandono or 0)
        resultado.append({
            "municipio": row.municipio,
            "ano": row.ano,
            "total_escolas": row.total_escolas,
            "total_matriculas": row.total_matriculas or 0,
            "aprovados": row.aprovados or 0,
            "reprovados": row.reprovados or 0,
            "abandono": row.abandono or 0,
            "transferidos": row.transferidos or 0,
            "taxa_aprovacao": round((row.aprovados / base) * 100, 2) if base > 0 else 0.0,
            "taxa_abandono": round((row.abandono / base) * 100, 2) if base > 0 else 0.0,
            "taxa_reprovacao": round((row.reprovados / base) * 100, 2) if base > 0 else 0.0,
        })
    return resultado


def _build_llm_context(db: Session, municipio: Optional[str], ano: Optional[int]) -> str:
    """Monta contexto textual com dados reais do banco para o LLM interpretar."""
    serie = carregar_serie_historica(db)
    return serie.resumo_para_llm(municipio=municipio, ano=ano)


# ── endpoints ────────────────────────────────────────────────────────────────

@dac_router.post("/importar")
async def importar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recebe um CSV, processa e persiste imediatamente."""
    conteudo = await file.read()
    resultado = importar_csv_bytes(conteudo, file.filename or "", db)
    return resultado


@dac_router.get("/status")
async def status(db: Session = Depends(get_db)):
    """Retorna quantos registros estão no banco DAC."""
    total_escolas = db.query(func.count(DacEscola.id)).scalar() or 0
    total_dados = db.query(func.count(DacDadosEscolares.id)).scalar() or 0
    anos = (
        db.query(distinct(DacDadosEscolares.ano))
        .order_by(DacDadosEscolares.ano)
        .all()
    )
    return {
        "total_escolas": total_escolas,
        "total_registros": total_dados,
        "anos_disponiveis": [a[0] for a in anos],
        "importado": total_dados > 0,
    }


@dac_router.get("/municipios")
async def listar_municipios(db: Session = Depends(get_db)):
    """Lista todos os municípios disponíveis no banco."""
    municipios = (
        db.query(distinct(DacEscola.municipio))
        .order_by(DacEscola.municipio)
        .all()
    )
    return [m[0] for m in municipios]


@dac_router.get("/anos")
async def listar_anos(db: Session = Depends(get_db)):
    """Lista os anos disponíveis."""
    anos = (
        db.query(distinct(DacDadosEscolares.ano))
        .order_by(DacDadosEscolares.ano)
        .all()
    )
    return [a[0] for a in anos]


@dac_router.get("/dashboard")
async def dashboard(
    municipio: Optional[str] = Query(None),
    ano: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Dados agregados para os gráficos do dashboard."""
    return _agregado_por_municipio_ano(db, municipio, ano)


@dac_router.get("/evolucao-estado")
async def evolucao_estado(db: Session = Depends(get_db)):
    """Evolução histórica agregada de todo o estado MS."""
    return _agregado_por_municipio_ano(db, municipio=None, ano=None)


@dac_router.get("/escolas")
async def listar_escolas(
    municipio: Optional[str] = Query(None),
    ano: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Lista escolas com seus dados, com filtros opcionais."""
    q = (
        db.query(DacEscola, DacDadosEscolares)
        .join(DacDadosEscolares, DacDadosEscolares.escola_id == DacEscola.id)
    )
    if municipio:
        q = q.filter(DacEscola.municipio == municipio)
    if ano:
        q = q.filter(DacDadosEscolares.ano == ano)

    q = q.order_by(DacDadosEscolares.total_matriculas.desc()).limit(limit)

    resultado = []
    for escola, dado in q.all():
        resultado.append({
            "escola": escola.nome,
            "municipio": escola.municipio,
            "ano": dado.ano,
            "total_matriculas": dado.total_matriculas,
            "aprovados": dado.aprovados,
            "reprovados": dado.reprovados,
            "abandono": dado.abandono,
            "taxa_aprovacao": dado.taxa_aprovacao,
            "taxa_abandono": dado.taxa_abandono,
        })
    return resultado


@dac_router.post("/chat")
async def chat_analitico(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat com LLM usando dados reais do banco como contexto.
    Aceita: { message, municipio?, ano? }
    Retorna: SSE streaming igual ao chat principal.
    """
    message = body.get("message", "").strip()
    municipio = body.get("municipio") or None
    ano = body.get("ano") or None
    if ano:
        try:
            ano = int(ano)
        except ValueError:
            ano = None

    if not message:
        return {"error": "Mensagem vazia"}

    contexto = _build_llm_context(db, municipio, ano)

    system_prompt = (
        "Você é um analista especialista em educação pública do estado de Mato Grosso do Sul (MS), "
        "com foco na ODS 4 (Educação de Qualidade) das Nações Unidas. "
        "Você interpreta dados reais de matrículas escolares e oferece análises objetivas, "
        "identifica tendências preocupantes e propõe soluções baseadas em evidências. "
        "Responda em português brasileiro, de forma clara e fundamentada nos dados fornecidos."
    )

    prompt_completo = (
        f"{system_prompt}\n\n"
        f"## Dados disponíveis:\n{contexto}\n\n"
        f"## Pergunta do usuário:\n{message}\n\n"
        f"## Sua análise:"
    )

    async def stream_response():
        llm = get_llm()
        try:
            async for chunk in llm.astream(prompt_completo):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
