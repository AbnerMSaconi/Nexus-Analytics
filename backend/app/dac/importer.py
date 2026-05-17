import csv
import io
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.dac.models import DacEscola, DacDadosEscolares

_CAMPOS = [
    "total_matriculas", "matricula_inicial", "matricula_apos_censo",
    "transferidos", "cancelados", "falecido", "abandono",
    "aprovados", "reprovados", "cursando", "outras_situacoes",
]

_MAP_ESCOLA = {
    "nomeunidadeescolar", "nomeuniesco", "unidadeescolar",
    "escola", "estabelecimento", "instituicao",
}
_MAP_MUNICIPIO = {
    "nomemunicipio", "municipio", "cidade", "local", "localidade",
}
_MAP_ANO = {"anoreferencia", "anoref", "ano", "year", "exercicio"}
_MAP_CAMPOS = {
    "matriculastotal":    "total_matriculas",
    "totalmatriculas":   "total_matriculas",
    "matriculainicial":  "matricula_inicial",
    "matriculaaposcenso": "matricula_apos_censo",
    "transferidos":      "transferidos",
    "cancelados":        "cancelados",
    "falecido":          "falecido",
    "falecidos":         "falecido",
    "abandono":          "abandono",
    "aprovados":         "aprovados",
    "reprovados":        "reprovados",
    "cursando":          "cursando",
    "outrassituacoes":   "outras_situacoes",
}


def _normalize(s: str) -> str:
    return (
        s.lower().strip()
        .replace(" ", "").replace("_", "").replace("-", "")
        .replace("ã", "a").replace("â", "a").replace("á", "a").replace("à", "a")
        .replace("ê", "e").replace("é", "e").replace("è", "e")
        .replace("í", "i").replace("î", "i")
        .replace("ó", "o").replace("ô", "o").replace("õ", "o")
        .replace("ú", "u").replace("û", "u")
        .replace("ç", "c")
    )


def _detect_encoding(data: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            data.decode(enc)
            return enc
        except Exception:
            pass
    return "utf-8"


def _detect_delimiter(sample: str) -> str:
    counts = {d: sample.count(d) for d in [";", ",", "\t", "|"]}
    best = max(counts, key=counts.get)
    return best if counts[best] > 2 else ","


def _to_int(val: str) -> int:
    try:
        return int(float(str(val).strip().replace(",", ".")))
    except Exception:
        return 0


def _parse_csv(conteudo: bytes) -> list[dict]:
    enc = _detect_encoding(conteudo)
    texto = conteudo.decode(enc, errors="replace")
    delim = _detect_delimiter(texto[:4000])
    reader = csv.DictReader(io.StringIO(texto), delimiter=delim)
    rows = list(reader)
    if not rows:
        return []
    raw_headers = list(rows[0].keys())
    clean_headers = [h.strip().lstrip("﻿") for h in raw_headers if h and h.strip()]
    if raw_headers != clean_headers:
        rows = [{h.strip().lstrip("﻿"): v for h, v in row.items()} for row in rows]
    return rows


def _detectar_mapa(headers: list[str]) -> dict:
    mapa = {"escola": None, "municipio": None, "ano": None, "campos": {}}
    for h in headers:
        n = _normalize(h)
        if n in _MAP_ESCOLA and mapa["escola"] is None:
            mapa["escola"] = h
        if n in _MAP_MUNICIPIO and mapa["municipio"] is None:
            mapa["municipio"] = h
        if n in _MAP_ANO and mapa["ano"] is None:
            mapa["ano"] = h
        if n in _MAP_CAMPOS:
            mapa["campos"][_MAP_CAMPOS[n]] = h
    return mapa


def _importar_rows(rows: list[dict], db: Session) -> dict:
    if not rows:
        return {"erro": "Nenhum registro encontrado."}

    mapa = _detectar_mapa(list(rows[0].keys()))
    col_escola    = mapa["escola"]
    col_municipio = mapa["municipio"]
    col_ano       = mapa["ano"]
    col_campos    = mapa["campos"]

    if not col_escola or not col_municipio or not col_ano:
        return {"erro": f"Colunas obrigatórias não encontradas (escola/municipio/ano). "
                        f"Colunas detectadas: {list(rows[0].keys())[:10]}"}

    # Carrega lookups existentes
    escola_lookup: dict[tuple, str] = {
        (e.nome, e.municipio): e.id
        for e in db.query(DacEscola).all()
    }
    dados_existentes: set[tuple] = {
        (d.escola_id, d.ano)
        for d in db.query(DacDadosEscolares.escola_id, DacDadosEscolares.ano).all()
    }

    novas_escolas: dict[tuple, str] = {}
    novos_dados: list[dict] = []
    ignorados = 0

    for row in rows:
        nome_escola   = row.get(col_escola, "").strip()
        nome_municipio = row.get(col_municipio, "").strip()
        if not nome_escola or not nome_municipio:
            continue

        try:
            ano = int(float(row.get(col_ano, "0").strip()))
        except Exception:
            continue
        if ano == 0:
            continue

        chave = (nome_escola, nome_municipio)
        if chave in escola_lookup:
            escola_id = escola_lookup[chave]
        elif chave in novas_escolas:
            escola_id = novas_escolas[chave]
        else:
            escola_id = str(uuid.uuid4())
            novas_escolas[chave] = escola_id

        if (escola_id, ano) in dados_existentes:
            ignorados += 1
            continue
        dados_existentes.add((escola_id, ano))

        dado: dict = {"id": str(uuid.uuid4()), "escola_id": escola_id, "ano": ano}
        for campo in _CAMPOS:
            col_csv = col_campos.get(campo)
            dado[campo] = _to_int(row.get(col_csv, "0")) if col_csv else 0

        novos_dados.append(dado)

    if novas_escolas:
        db.execute(
            DacEscola.__table__.insert(),
            [{"id": id_, "nome": nome, "municipio": municipio}
             for (nome, municipio), id_ in novas_escolas.items()],
        )
    if novos_dados:
        db.execute(DacDadosEscolares.__table__.insert(), novos_dados)

    db.commit()

    return {
        "status": "ok",
        "registros_inseridos": len(novos_dados),
        "registros_ignorados": ignorados,
        "escolas_novas": len(novas_escolas),
    }


def importar_csv_bytes(conteudo: bytes, filename: str, db: Session) -> dict:
    return _importar_rows(_parse_csv(conteudo), db)


def importar_varios_csv_bytes(arquivos: list, db: Session) -> dict:
    all_rows: list[dict] = []
    for _filename, conteudo in arquivos:
        all_rows.extend(_parse_csv(conteudo))
    return _importar_rows(all_rows, db)


def get_progresso() -> dict:
    return {"status": "idle", "etapa": "", "pct": 0}
