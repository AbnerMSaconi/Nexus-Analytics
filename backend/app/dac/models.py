import uuid
from sqlalchemy import Column, String, Integer, UniqueConstraint, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


class DacEscola(Base):
    __tablename__ = "dac_escolas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = Column(String, nullable=False)
    municipio = Column(String, nullable=False, index=True)

    dados = relationship(
        "DacDadosEscolares", back_populates="escola", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("nome", "municipio", name="uq_escola_nome_municipio"),
    )


class DacDadosEscolares(Base):
    __tablename__ = "dac_dados_escolares"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    escola_id = Column(String, ForeignKey("dac_escolas.id"), nullable=False, index=True)
    ano = Column(Integer, nullable=False, index=True)

    total_matriculas  = Column(Integer, default=0)
    matricula_inicial = Column(Integer, default=0)
    matricula_apos_censo = Column(Integer, default=0)
    transferidos      = Column(Integer, default=0)
    cancelados        = Column(Integer, default=0)
    falecido          = Column(Integer, default=0)
    abandono          = Column(Integer, default=0)
    aprovados         = Column(Integer, default=0)
    reprovados        = Column(Integer, default=0)
    cursando          = Column(Integer, default=0)
    outras_situacoes  = Column(Integer, default=0)

    escola = relationship("DacEscola", back_populates="dados")

    __table_args__ = (
        UniqueConstraint("escola_id", "ano", name="uq_dados_escola_ano"),
    )
