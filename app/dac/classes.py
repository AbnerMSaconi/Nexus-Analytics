from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DadoAnual:
    ano: int
    total_matriculas: int
    matricula_inicial: int
    matricula_apos_censo: int
    transferidos: int
    cancelados: int
    falecido: int
    abandono: int
    aprovados: int
    reprovados: int
    cursando: int
    outras_situacoes: int = 0

    def taxa_aprovacao(self) -> float:
        base = self.aprovados + self.reprovados + self.abandono
        return round((self.aprovados / base) * 100, 2) if base > 0 else 0.0

    def taxa_abandono(self) -> float:
        base = self.aprovados + self.reprovados + self.abandono
        return round((self.abandono / base) * 100, 2) if base > 0 else 0.0

    def taxa_reprovacao(self) -> float:
        base = self.aprovados + self.reprovados + self.abandono
        return round((self.reprovados / base) * 100, 2) if base > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "ano": self.ano,
            "total_matriculas": self.total_matriculas,
            "aprovados": self.aprovados,
            "reprovados": self.reprovados,
            "abandono": self.abandono,
            "transferidos": self.transferidos,
            "cancelados": self.cancelados,
            "cursando": self.cursando,
            "outras_situacoes": self.outras_situacoes,
            "taxa_aprovacao": self.taxa_aprovacao(),
            "taxa_abandono": self.taxa_abandono(),
            "taxa_reprovacao": self.taxa_reprovacao(),
        }


class Escola:
    def __init__(self, nome: str, municipio: str):
        self.nome = nome
        self.municipio = municipio
        self.historico: dict[int, DadoAnual] = {}

    def adicionar_dado(self, dado: DadoAnual) -> None:
        self.historico[dado.ano] = dado

    def get_dado_ano(self, ano: int) -> Optional[DadoAnual]:
        return self.historico.get(ano)

    def anos_disponiveis(self) -> list[int]:
        return sorted(self.historico.keys())

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "municipio": self.municipio,
            "historico": [d.to_dict() for d in sorted(self.historico.values(), key=lambda x: x.ano)],
        }


class Municipio:
    def __init__(self, nome: str):
        self.nome = nome
        self.escolas: dict[str, Escola] = {}

    def adicionar_escola(self, escola: Escola) -> None:
        self.escolas[escola.nome] = escola

    def get_escola(self, nome: str) -> Optional[Escola]:
        return self.escolas.get(nome)

    def total_matriculas(self, ano: int) -> int:
        return sum(
            e.get_dado_ano(ano).total_matriculas
            for e in self.escolas.values() if e.get_dado_ano(ano)
        )

    def total_aprovados(self, ano: int) -> int:
        return sum(
            e.get_dado_ano(ano).aprovados
            for e in self.escolas.values() if e.get_dado_ano(ano)
        )

    def total_reprovados(self, ano: int) -> int:
        return sum(
            e.get_dado_ano(ano).reprovados
            for e in self.escolas.values() if e.get_dado_ano(ano)
        )

    def total_abandono(self, ano: int) -> int:
        return sum(
            e.get_dado_ano(ano).abandono
            for e in self.escolas.values() if e.get_dado_ano(ano)
        )

    def taxa_aprovacao(self, ano: int) -> float:
        ap = self.total_aprovados(ano)
        base = ap + self.total_reprovados(ano) + self.total_abandono(ano)
        return round((ap / base) * 100, 2) if base > 0 else 0.0

    def taxa_abandono(self, ano: int) -> float:
        ab = self.total_abandono(ano)
        base = self.total_aprovados(ano) + self.total_reprovados(ano) + ab
        return round((ab / base) * 100, 2) if base > 0 else 0.0

    def resumo_ano(self, ano: int) -> dict:
        return {
            "municipio": self.nome,
            "ano": ano,
            "total_escolas": len(self.escolas),
            "total_matriculas": self.total_matriculas(ano),
            "aprovados": self.total_aprovados(ano),
            "reprovados": self.total_reprovados(ano),
            "abandono": self.total_abandono(ano),
            "taxa_aprovacao": self.taxa_aprovacao(ano),
            "taxa_abandono": self.taxa_abandono(ano),
        }

    def evolucao(self, anos: list[int]) -> list[dict]:
        return [self.resumo_ano(a) for a in anos if self.total_matriculas(a) > 0]


class SerieHistorica:
    def __init__(self):
        self.municipios: dict[str, Municipio] = {}
        self._anos: set[int] = set()

    def _get_ou_criar_municipio(self, nome: str) -> Municipio:
        if nome not in self.municipios:
            self.municipios[nome] = Municipio(nome)
        return self.municipios[nome]

    def adicionar_registro(self, municipio_nome: str, escola_nome: str, dado: DadoAnual) -> None:
        municipio = self._get_ou_criar_municipio(municipio_nome)
        escola = municipio.get_escola(escola_nome)
        if escola is None:
            escola = Escola(escola_nome, municipio_nome)
            municipio.adicionar_escola(escola)
        escola.adicionar_dado(dado)
        self._anos.add(dado.ano)

    def anos_disponiveis(self) -> list[int]:
        return sorted(self._anos)

    def lista_municipios(self) -> list[str]:
        return sorted(self.municipios.keys())

    def total_registros(self) -> int:
        return sum(len(e.historico) for m in self.municipios.values() for e in m.escolas.values())

    def evolucao_estado(self) -> list[dict]:
        resultado = []
        for ano in self.anos_disponiveis():
            total_ap = sum(m.total_aprovados(ano) for m in self.municipios.values())
            total_rep = sum(m.total_reprovados(ano) for m in self.municipios.values())
            total_ab = sum(m.total_abandono(ano) for m in self.municipios.values())
            base = total_ap + total_rep + total_ab
            resultado.append({
                "ano": ano,
                "total_matriculas": sum(m.total_matriculas(ano) for m in self.municipios.values()),
                "aprovados": total_ap,
                "reprovados": total_rep,
                "abandono": total_ab,
                "taxa_aprovacao": round((total_ap / base) * 100, 2) if base > 0 else 0.0,
                "taxa_abandono": round((total_ab / base) * 100, 2) if base > 0 else 0.0,
                "taxa_reprovacao": round((total_rep / base) * 100, 2) if base > 0 else 0.0,
            })
        return resultado

    def dados_municipio(self, nome: str) -> list[dict]:
        municipio = self.municipios.get(nome)
        if not municipio:
            return []
        return municipio.evolucao(self.anos_disponiveis())

    def resumo_para_llm(self, municipio: Optional[str] = None, ano: Optional[int] = None) -> str:
        """Gera um resumo textual dos dados para ser injetado como contexto no LLM."""
        linhas = ["# Dados da Rede Pública de Ensino - Mato Grosso do Sul\n"]

        if municipio and ano:
            m = self.municipios.get(municipio)
            if m:
                r = m.resumo_ano(ano)
                linhas.append(f"## {municipio} — {ano}")
                linhas.append(f"- Escolas: {r['total_escolas']}")
                linhas.append(f"- Matrículas: {r['total_matriculas']:,}")
                linhas.append(f"- Aprovados: {r['aprovados']:,} ({r['taxa_aprovacao']}%)")
                linhas.append(f"- Reprovados: {r['reprovados']:,}")
                linhas.append(f"- Abandono: {r['abandono']:,} ({r['taxa_abandono']}%)")
        elif municipio:
            m = self.municipios.get(municipio)
            if m:
                linhas.append(f"## Evolução histórica: {municipio}")
                for d in m.evolucao(self.anos_disponiveis()):
                    linhas.append(
                        f"- {d['ano']}: {d['total_matriculas']:,} matrículas | "
                        f"Aprovação: {d['taxa_aprovacao']}% | Abandono: {d['taxa_abandono']}%"
                    )
        elif ano:
            linhas.append(f"## Todos os municípios — {ano}")
            municipios_ano = []
            for nome_m, m in self.municipios.items():
                r = m.resumo_ano(ano)
                if r["total_matriculas"] > 0:
                    municipios_ano.append(r)
            municipios_ano.sort(key=lambda x: x["total_matriculas"], reverse=True)
            for r in municipios_ano[:20]:
                linhas.append(
                    f"- {r['municipio']}: {r['total_matriculas']:,} matrículas | "
                    f"Aprovação: {r['taxa_aprovacao']}% | Abandono: {r['taxa_abandono']}%"
                )
        else:
            linhas.append("## Evolução do Estado (2018-2026)")
            for d in self.evolucao_estado():
                linhas.append(
                    f"- {d['ano']}: {d['total_matriculas']:,} matrículas | "
                    f"Aprovação: {d['taxa_aprovacao']}% | Abandono: {d['taxa_abandono']}% | "
                    f"Reprovação: {d['taxa_reprovacao']}%"
                )

        return "\n".join(linhas)
