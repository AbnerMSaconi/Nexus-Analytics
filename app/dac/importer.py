import csv
import io
import uuid
from sqlalchemy.orm import Session
from app.dac.classes import DadoAnual, SerieHistorica
from app.dac.models import DacEscola, DacDadosEscolares


def _safe_int(value) -> int:
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return 0


def _calcular_taxas(ap: int, rep: int, ab: int) -> tuple[float, float, float]:
    base = ap + rep + ab
    if base == 0:
        return 0.0, 0.0, 0.0
    return round(ap/base*100, 2), round(ab/base*100, 2), round(rep/base*100, 2)


def importar_csv_bytes(conteudo: bytes, filename: str, db: Session) -> dict:
    """Processa um CSV enviado como bytes e persiste no banco via bulk insert."""

    # Tenta extrair ano do nome do arquivo (ex: matriculas-...-2021.csv)
    ano_filename = 0
    for part in filename.replace(".csv", "").split("-"):
        if part.isdigit() and len(part) == 4:
            ano_filename = int(part)
            break

    texto = conteudo.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(texto), delimiter=";")

    registros: list[dict] = []
    for row in reader:
        municipio  = row.get("NomeMunicipio", "").strip()
        escola_nome = row.get("NomeUnidadeEscolar", "").strip()
        if not municipio or not escola_nome:
            continue

        ano = _safe_int(row.get("AnoReferencia", ano_filename)) or ano_filename
        ap  = _safe_int(row.get("Aprovados", 0))
        rep = _safe_int(row.get("Reprovados", 0))
        ab  = _safe_int(row.get("Abandono", 0))
        taxa_ap, taxa_ab, taxa_rep = _calcular_taxas(ap, rep, ab)

        registros.append({
            "municipio":           municipio,
            "escola":              escola_nome,
            "ano":                 ano,
            "total_matriculas":    _safe_int(row.get("MatriculasTotal", 0)),
            "matricula_inicial":   _safe_int(row.get("MatriculaInicial", 0)),
            "matricula_apos_censo":_safe_int(row.get("MatriculaAposCenso", 0)),
            "transferidos":        _safe_int(row.get("Transferidos", 0)),
            "cancelados":          _safe_int(row.get("Cancelados", 0)),
            "falecido":            _safe_int(row.get("Falecido", 0)),
            "abandono":            ab,
            "aprovados":           ap,
            "reprovados":          rep,
            "cursando":            _safe_int(row.get("Cursando", 0)),
            "outras_situacoes":    _safe_int(row.get("OutrasSituacoes", 0)),
            "taxa_aprovacao":      taxa_ap,
            "taxa_abandono":       taxa_ab,
            "taxa_reprovacao":     taxa_rep,
        })

    if not registros:
        return {"erro": "Nenhum registro válido encontrado no arquivo."}

    # ── Bulk insert escolas ──────────────────────────────────────────────────
    escolas_existentes = {
        (e.nome, e.municipio): e.id
        for e in db.query(DacEscola).all()
    }

    pares_unicos = {(r["escola"], r["municipio"]) for r in registros}
    novas_escolas = []
    for nome, municipio in pares_unicos:
        if (nome, municipio) not in escolas_existentes:
            eid = str(uuid.uuid4())
            escolas_existentes[(nome, municipio)] = eid
            novas_escolas.append({"id": eid, "nome": nome, "municipio": municipio})

    if novas_escolas:
        db.execute(DacEscola.__table__.insert(), novas_escolas)
        db.flush()

    # ── Bulk insert dados ────────────────────────────────────────────────────
    existentes = {
        (d.escola_id, d.ano)
        for d in db.query(DacDadosEscolares.escola_id, DacDadosEscolares.ano).all()
    }

    novos = []
    ignorados = 0
    for r in registros:
        eid = escolas_existentes.get((r["escola"], r["municipio"]))
        if not eid or (eid, r["ano"]) in existentes:
            ignorados += 1
            continue
        existentes.add((eid, r["ano"]))
        novos.append({
            "id":                  str(uuid.uuid4()),
            "escola_id":           eid,
            "ano":                 r["ano"],
            "total_matriculas":    r["total_matriculas"],
            "matricula_inicial":   r["matricula_inicial"],
            "matricula_apos_censo":r["matricula_apos_censo"],
            "transferidos":        r["transferidos"],
            "cancelados":          r["cancelados"],
            "falecido":            r["falecido"],
            "abandono":            r["abandono"],
            "aprovados":           r["aprovados"],
            "reprovados":          r["reprovados"],
            "cursando":            r["cursando"],
            "outras_situacoes":    r["outras_situacoes"],
            "taxa_aprovacao":      r["taxa_aprovacao"],
            "taxa_abandono":       r["taxa_abandono"],
            "taxa_reprovacao":     r["taxa_reprovacao"],
        })

    if novos:
        db.execute(DacDadosEscolares.__table__.insert(), novos)

    db.commit()

    return {
        "status": "ok",
        "arquivo": filename,
        "ano": ano_filename or (registros[0]["ano"] if registros else "?"),
        "registros_inseridos": len(novos),
        "registros_ignorados": ignorados,
        "escolas_novas": len(novas_escolas),
    }


# mantido para compatibilidade
def get_progresso() -> dict:
    return {"status": "idle", "etapa": "", "pct": 0}


def carregar_serie_historica(db: Session) -> SerieHistorica:
    serie = SerieHistorica()
    for escola in db.query(DacEscola).all():
        for d in escola.dados:
            serie.adicionar_registro(
                escola.municipio, escola.nome,
                DadoAnual(
                    ano=d.ano,
                    total_matriculas=d.total_matriculas,
                    matricula_inicial=d.matricula_inicial,
                    matricula_apos_censo=d.matricula_apos_censo,
                    transferidos=d.transferidos,
                    cancelados=d.cancelados,
                    falecido=d.falecido,
                    abandono=d.abandono,
                    aprovados=d.aprovados,
                    reprovados=d.reprovados,
                    cursando=d.cursando,
                    outras_situacoes=d.outras_situacoes,
                ),
            )
    return serie
