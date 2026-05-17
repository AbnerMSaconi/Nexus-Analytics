import json
import base64
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import distinct, func
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.llm import get_llm
from app.api.models import User
from app.dac.models import DacEscola, DacDadosEscolares
from app.dac.importer import importar_csv_bytes, importar_varios_csv_bytes
from app.dac.classes import DadoAnual, SerieHistorica

dac_router = APIRouter(prefix="/dac", tags=["Nexus - Análise de Dados"])

_CAMPOS_NUM = [
    "total_matriculas", "matricula_inicial", "matricula_apos_censo",
    "transferidos", "cancelados", "falecido", "abandono",
    "aprovados", "reprovados", "cursando", "outras_situacoes",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _query_dados(
    db: Session,
    municipio: Optional[str],
    ano_inicio: Optional[int],
    ano_fim: Optional[int],
):
    q = db.query(DacDadosEscolares)
    if municipio:
        ids = db.query(DacEscola.id).filter(DacEscola.municipio == municipio).subquery()
        q = q.filter(DacDadosEscolares.escola_id.in_(ids))
    if ano_inicio:
        q = q.filter(DacDadosEscolares.ano >= ano_inicio)
    if ano_fim:
        q = q.filter(DacDadosEscolares.ano <= ano_fim)
    return q


def _aggregate(rows) -> dict[int, dict]:
    grupos: dict[int, dict] = defaultdict(
        lambda: {c: 0 for c in _CAMPOS_NUM} | {"_escolas": 0}
    )
    for d in rows:
        g = grupos[d.ano]
        g["_escolas"] += 1
        for c in _CAMPOS_NUM:
            g[c] += getattr(d, c, 0)
    return grupos


def _build_result(grupos: dict[int, dict]) -> list[dict]:
    resultado = []
    for ano in sorted(grupos):
        g = grupos[ano]
        base = g["aprovados"] + g["reprovados"] + g["abandono"]
        row = {
            "ano": ano,
            "total_escolas": g["_escolas"],
            **{c: g[c] for c in _CAMPOS_NUM},
            "taxa_aprovacao":  round(g["aprovados"]  / base * 100, 2) if base > 0 else 0.0,
            "taxa_reprovacao": round(g["reprovados"] / base * 100, 2) if base > 0 else 0.0,
            "taxa_abandono":   round(g["abandono"]   / base * 100, 2) if base > 0 else 0.0,
        }
        resultado.append(row)
    return resultado


def _build_context(
    db: Session,
    municipio: Optional[str],
    ano_inicio: Optional[int],
    ano_fim: Optional[int],
) -> str:
    # Carrega dados + escola em join para evitar N+1
    q = (
        db.query(DacDadosEscolares, DacEscola)
        .join(DacEscola, DacDadosEscolares.escola_id == DacEscola.id)
    )
    if municipio:
        q = q.filter(DacEscola.municipio == municipio)
    if ano_inicio:
        q = q.filter(DacDadosEscolares.ano >= ano_inicio)
    if ano_fim:
        q = q.filter(DacDadosEscolares.ano <= ano_fim)

    total = q.count()
    if total == 0:
        return "Nenhum dado encontrado para os filtros selecionados."

    serie = SerieHistorica()
    for dados, escola in q.yield_per(1000):
        dado = DadoAnual(
            ano=dados.ano,
            total_matriculas=dados.total_matriculas,
            matricula_inicial=dados.matricula_inicial,
            matricula_apos_censo=dados.matricula_apos_censo,
            transferidos=dados.transferidos,
            cancelados=dados.cancelados,
            falecido=dados.falecido,
            abandono=dados.abandono,
            aprovados=dados.aprovados,
            reprovados=dados.reprovados,
            cursando=dados.cursando,
            outras_situacoes=dados.outras_situacoes,
        )
        serie.adicionar_registro(escola.municipio, escola.nome, dado)

    ano_filtro = ano_inicio if (ano_inicio and ano_inicio == ano_fim) else None
    return serie.resumo_para_llm(municipio=municipio, ano=ano_filtro) + f"\n\nTotal de registros: {total}"


# ── endpoints ─────────────────────────────────────────────────────────────────

@dac_router.post("/importar")
async def importar(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    files = body.get("files", [])
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    arquivos = []
    for fd in files:
        name = fd.get("name", "arquivo.csv")
        try:
            conteudo = base64.b64decode(fd.get("content", ""))
            arquivos.append((name, conteudo))
        except Exception:
            raise HTTPException(status_code=400, detail=f"Erro ao decodificar {name}")

    if len(arquivos) == 1:
        return importar_csv_bytes(arquivos[0][1], arquivos[0][0], db)

    if body.get("mesclar", True):
        return importar_varios_csv_bytes(arquivos, db)

    resultados = [importar_csv_bytes(c, n, db) for n, c in arquivos]
    return {
        "status": "ok",
        "arquivos": len(arquivos),
        "registros_inseridos": sum(r.get("registros_inseridos", 0) for r in resultados),
        "registros_ignorados": sum(r.get("registros_ignorados", 0) for r in resultados),
        "escolas_novas":       sum(r.get("escolas_novas", 0) for r in resultados),
    }


@dac_router.get("/status")
async def status(db: Session = Depends(get_db)):
    total_escolas   = db.query(func.count(DacEscola.id)).scalar() or 0
    total_registros = db.query(func.count(DacDadosEscolares.id)).scalar() or 0
    anos = sorted(
        r[0] for r in db.query(distinct(DacDadosEscolares.ano)).all() if r[0]
    )
    return {
        "total_escolas": total_escolas,
        "total_registros": total_registros,
        "anos_disponiveis": anos,
        "importado": total_registros > 0,
    }


@dac_router.get("/anos")
async def listar_anos(db: Session = Depends(get_db)):
    rows = db.query(distinct(DacDadosEscolares.ano)).order_by(DacDadosEscolares.ano).all()
    return sorted(r[0] for r in rows if r[0])


@dac_router.get("/municipios")
async def listar_municipios(db: Session = Depends(get_db)):
    rows = db.query(distinct(DacEscola.municipio)).order_by(DacEscola.municipio).all()
    return [r[0] for r in rows if r[0]]


@dac_router.get("/dashboard")
async def dashboard(
    municipio: Optional[str] = Query(None),
    ano_inicio: Optional[int] = Query(None),
    ano_fim: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = _query_dados(db, municipio, ano_inicio, ano_fim)
    return _build_result(_aggregate(q.yield_per(2000)))


@dac_router.delete("/dados/{ano}")
async def deletar_ano(
    ano: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    removed = db.query(DacDadosEscolares).filter(DacDadosEscolares.ano == ano).delete()
    db.commit()
    return {"status": "ok", "ano": ano, "registros_removidos": removed}


@dac_router.post("/chat")
async def chat_analitico(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message    = body.get("message", "").strip()
    municipio  = body.get("municipio") or None
    ano_inicio = body.get("ano_inicio") or None
    ano_fim    = body.get("ano_fim") or None

    if not message:
        return {"error": "Mensagem vazia"}

    filtros = []
    if ano_inicio or ano_fim:
        filtros.append(f"Período: de {ano_inicio or 'início'} a {ano_fim or 'fim'}")
    else:
        filtros.append("Período: todos os disponíveis (2018–2026)")
    filtros.append(f"Município: {municipio}" if municipio else "Município: todos")

    contexto = _build_context(db, municipio, ano_inicio, ano_fim)

    prompt = (
        "Você é Nexus, um assistente especializado em análise de dados educacionais da rede pública "
        "do Mato Grosso do Sul. Interprete os dados fornecidos e responda de forma objetiva, clara "
        "e fundamentada. Quando o usuário disser 'nesse período', 'nesse município', 'esses dados' "
        "ou termos similares, refira-se SEMPRE aos filtros ativos — nunca invente valores. "
        "Responda em português brasileiro.\n\n"
        f"## Filtros ativos:\n" + "\n".join(f"- {f}" for f in filtros) + "\n\n"
        f"## Dados disponíveis:\n{contexto}\n\n"
        f"## Pergunta:\n{message}\n\n"
        "## Análise:"
    )

    async def stream_response():
        llm = get_llm()
        try:
            async for chunk in llm.astream(prompt):
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
