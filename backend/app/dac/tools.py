import json
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import distinct

from app.dac.models import DacEscola, DacDadosEscolares

_CAMPOS_NUM = [
    "total_matriculas", "matricula_inicial", "matricula_apos_censo",
    "transferidos", "cancelados", "falecido", "abandono",
    "aprovados", "reprovados", "cursando", "outras_situacoes",
]

# ── Definições das ferramentas (OpenAI tool calling format) ───────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_dados",
            "description": (
                "Busca e agrega dados educacionais da rede pública do Mato Grosso do Sul. "
                "Retorna totais e taxas por ano, além de totais acumulados do período. "
                "Use sempre que precisar de números reais para responder a pergunta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ano_inicio": {
                        "type": "integer",
                        "description": "Ano inicial do período (inclusive). Omita para incluir desde o primeiro ano disponível."
                    },
                    "ano_fim": {
                        "type": "integer",
                        "description": "Ano final do período (inclusive). Omita para incluir até o último ano disponível."
                    },
                    "municipio": {
                        "type": "string",
                        "description": "Nome exato do município. Omita para agregar todos os municípios."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_anos",
            "description": "Lista os anos disponíveis na base de dados. Use antes de responder perguntas sobre períodos para não citar anos inexistentes.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_municipios",
            "description": "Lista todos os municípios disponíveis na base de dados.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

# ── Executores ────────────────────────────────────────────────────────────────

def executar_tool(name: str, args: dict, db: Session) -> str:
    if name == "listar_anos":
        anos = sorted(r[0] for r in db.query(DacDadosEscolares.ano).distinct().all() if r[0])
        return json.dumps({"anos_disponiveis": anos})

    if name == "listar_municipios":
        municipios = sorted(r[0] for r in db.query(DacEscola.municipio).distinct().all() if r[0])
        return json.dumps({"municipios": municipios})

    if name == "buscar_dados":
        ano_inicio = args.get("ano_inicio")
        ano_fim    = args.get("ano_fim")
        municipio  = args.get("municipio")

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

        grupos: dict[int, dict] = defaultdict(lambda: {c: 0 for c in _CAMPOS_NUM})
        for dados, _ in q.yield_per(2000):
            g = grupos[dados.ano]
            for c in _CAMPOS_NUM:
                g[c] += getattr(dados, c, 0) or 0

        if not grupos:
            return json.dumps({"erro": "Nenhum dado encontrado para os filtros informados."})

        por_ano = []
        acc = {c: 0 for c in ("total_matriculas", "aprovados", "reprovados", "abandono")}

        for ano in sorted(grupos):
            g = grupos[ano]
            base = g["aprovados"] + g["reprovados"] + g["abandono"]
            row = {
                "ano": ano,
                "total_matriculas": g["total_matriculas"],
                "aprovados":  g["aprovados"],
                "reprovados": g["reprovados"],
                "abandono":   g["abandono"],
                "taxa_aprovacao":  round(g["aprovados"]  / base * 100, 2) if base else 0.0,
                "taxa_reprovacao": round(g["reprovados"] / base * 100, 2) if base else 0.0,
                "taxa_abandono":   round(g["abandono"]   / base * 100, 2) if base else 0.0,
            }
            por_ano.append(row)
            for c in acc:
                acc[c] += g[c]

        base_total = acc["aprovados"] + acc["reprovados"] + acc["abandono"]
        totais = {
            "total_matriculas":        acc["total_matriculas"],
            "total_aprovados":         acc["aprovados"],
            "total_reprovados":        acc["reprovados"],
            "total_abandono":          acc["abandono"],
            "taxa_aprovacao_periodo":  round(acc["aprovados"]  / base_total * 100, 2) if base_total else 0.0,
            "taxa_reprovacao_periodo": round(acc["reprovados"] / base_total * 100, 2) if base_total else 0.0,
            "taxa_abandono_periodo":   round(acc["abandono"]   / base_total * 100, 2) if base_total else 0.0,
        }

        return json.dumps({"por_ano": por_ano, "totais_periodo": totais}, ensure_ascii=False)

    return json.dumps({"erro": f"Ferramenta desconhecida: {name}"})
