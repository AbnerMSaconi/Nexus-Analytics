import json
import base64
import httpx
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import distinct, func
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.api.models import User
from app.dac.models import DacEscola, DacDadosEscolares
from app.dac.importer import importar_csv_bytes, importar_varios_csv_bytes
from app.dac.classes import DadoAnual, SerieHistorica
from app.dac.tools import executar_tool

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


_LLM_URL = str(settings.LLM_BASE_URL).rstrip("/") + "/chat/completions"

_re = __import__("re")
# Exclusão: aceita até 50 chars entre a palavra e o ano ("desconsidere os dados de 2026")
_RE_EXCLUIR  = _re.compile(r"(desconsider\w*|exclu\w*|ignor\w*|retir\w*|sem\b).{0,50}?\b(20\d{2})\b", _re.I)
_RE_PERIODO  = _re.compile(r"(?:de\s+)?(\d{4})\s*(?:a|até|ate|-)\s*(\d{4})", _re.I)
_RE_ANO_UNICO = _re.compile(r"\b(20\d{2})\b")


def _inferir_filtros(message: str, history: list, db: Session) -> tuple[Optional[int], Optional[int], Optional[str]]:
    anos_disponiveis = sorted(r[0] for r in db.query(DacDadosEscolares.ano).distinct().all() if r[0])
    if not anos_disponiveis:
        return None, None, None

    texto = message + " " + " ".join(m.get("content", "") for m in history[-6:])

    excluir = _RE_EXCLUIR.search(texto)
    if excluir:
        ano_excluir = int(excluir.group(2))
        restantes = [a for a in anos_disponiveis if a != ano_excluir]
        if restantes:
            return restantes[0], restantes[-1], None

    periodo = _RE_PERIODO.search(message)
    if periodo:
        return int(periodo.group(1)), int(periodo.group(2)), None

    anos_citados = [int(a) for a in _RE_ANO_UNICO.findall(message) if int(a) in anos_disponiveis]
    if len(anos_citados) == 1:
        return anos_citados[0], anos_citados[0], None

    # Ano-alvo fora da base (ex: estimativa para 2025) → envia dados até o ano anterior
    _RE_ESTIM = _re.compile(r"\b(estimativ|project|prever|predi|forecast)\w*\b.{0,60}?\b(20\d{2})\b", _re.I)
    estim = _RE_ESTIM.search(texto)
    if estim:
        ano_alvo = int(estim.group(2))
        if ano_alvo not in anos_disponiveis:
            anteriores = [a for a in anos_disponiveis if a < ano_alvo]
            if anteriores:
                return anteriores[0], anteriores[-1], None

    return None, None, None


def _formatar_contexto(dados_json: str, anos_presentes: list) -> str:
    """Converte o JSON da query em texto legível para o LLM."""
    try:
        dados = json.loads(dados_json)
    except Exception:
        return dados_json

    if "erro" in dados:
        return f"Nenhum dado encontrado: {dados['erro']}"

    linhas = [f"Anos disponíveis na base: {anos_presentes}\n"]

    por_ano = dados.get("por_ano", [])
    if por_ano:
        linhas.append("Dados por ano:")
        for r in por_ano:
            linhas.append(
                f"  {r['ano']}: {r['total_matriculas']:,} matrículas | "
                f"Aprovados: {r['aprovados']:,} ({r['taxa_aprovacao']}%) | "
                f"Reprovados: {r['reprovados']:,} ({r['taxa_reprovacao']}%) | "
                f"Abandono: {r['abandono']:,} ({r['taxa_abandono']}%)"
            )

    t = dados.get("totais_periodo", {})
    if t:
        base = t.get('total_aprovados', 0) + t.get('total_reprovados', 0) + t.get('total_abandono', 0)
        linhas.append("\nTotais acumulados do período (USE ESTES VALORES — NÃO RECALCULE):")
        linhas.append(f"  Matrículas totais:   {t.get('total_matriculas', 0):,}")
        linhas.append(f"  Total aprovados:     {t.get('total_aprovados', 0):,}")
        linhas.append(f"  Total reprovados:    {t.get('total_reprovados', 0):,}")
        linhas.append(f"  Total abandono:      {t.get('total_abandono', 0):,}")
        linhas.append(f"  Base de cálculo:     {base:,} (aprovados + reprovados + abandono)")
        linhas.append(f"  Taxa aprovação:      {t.get('taxa_aprovacao_periodo', 0)}%  ← RESPOSTA PRONTA")
        linhas.append(f"  Taxa reprovação:     {t.get('taxa_reprovacao_periodo', 0)}%  ← RESPOSTA PRONTA")
        linhas.append(f"  Taxa abandono:       {t.get('taxa_abandono_periodo', 0)}%  ← RESPOSTA PRONTA")

    return "\n".join(linhas)


@dac_router.post("/chat")
async def chat_analitico(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message       = body.get("message", "").strip()
    history       = body.get("history", [])
    thinking_mode = body.get("thinking_mode", False)
    municipio  = body.get("municipio") or None
    ano_inicio = body.get("ano_inicio") or None
    ano_fim    = body.get("ano_fim") or None

    if not message:
        return {"error": "Mensagem vazia"}

    if not ano_inicio and not ano_fim:
        inf_inicio, inf_fim, inf_mun = _inferir_filtros(message, history, db)
        ano_inicio = inf_inicio
        ano_fim    = inf_fim
        municipio  = municipio or inf_mun

    dados_json = executar_tool("buscar_dados", {
        "ano_inicio": ano_inicio,
        "ano_fim": ano_fim,
        **({"municipio": municipio} if municipio else {}),
    }, db)

    anos_presentes = sorted(r[0] for r in db.query(DacDadosEscolares.ano).distinct().all() if r[0])
    contexto = _formatar_contexto(dados_json, anos_presentes)

    think_token = "/think" if thinking_mode else "/no_think"

    # Com raciocínio ativo o modelo gasta muitos tokens no <think>.
    # Reduzimos histórico e tamanho das mensagens para não lotar o contexto.
    if thinking_mode:
        hist_limit   = 4
        hist_max_len = 300
    else:
        hist_limit   = 8
        hist_max_len = 600

    system_prompt = (
        f"{think_token}\n"
        "Você é Nexus, assistente especializado em dados educacionais da rede pública do MS.\n\n"
        "REGRAS:\n"
        "1. Para análise de dados reais: use SOMENTE os números do CONTEXTO.\n"
        "2. Para estimativas/projeções EXPLICITAMENTE pedidas pelo usuário: aplique tendência "
        "linear ou média móvel com base nos dados do CONTEXTO e deixe claro que é uma projeção.\n"
        "3. Taxas do período estão marcadas com '← RESPOSTA PRONTA'. Copie-as diretamente, não recalcule.\n"
        "4. Responda em português brasileiro, de forma direta e objetiva.\n"
        "5. Use LaTeX para fórmulas: $...$ inline, $$...$$ em bloco.\n\n"
        f"CONTEXTO:\n{contexto}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-hist_limit:]:
        role = "user" if m.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": str(m.get("content", ""))[:hist_max_len]})
    messages.append({"role": "user", "content": message})

    async def stream_response():
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream("POST", _LLM_URL, json={
                    "model": settings.MODEL_NAME,
                    "messages": messages,
                    "temperature": settings.TEMPERATURE,
                    "max_tokens": settings.MAX_TOKENS,
                    "stream": True,
                }) as stream:
                    async for line in stream.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw)
                            token = chunk["choices"][0].get("delta", {}).get("content") or ""
                            if token:
                                yield f"data: {json.dumps({'type': 'chunk', 'content': token})}\n\n"
                        except Exception:
                            pass
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            finally:
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
