# app/api/models.py
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Boolean, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

# ### INICIO DA DEFINICAO DE USUARIOS COM PERMISSOES ###
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True) # A senha já é armazenada como hash (segurança padrão)
    
    # --- NOVOS CAMPOS DE CONTROLE DE ACESSO (RBAC) ---
    role = Column(String, default="aluno") # Opcoes: 'aluno', 'professor', 'coordenador', 'administrador'
    course = Column(String, nullable=True) # Ex: 'Direito', 'Engenharia'. Essencial para restringir alunos.
    
    # --- NOVOS CAMPOS DE SEGURANCA E BLOQUEIO ---
    is_blocked = Column(Boolean, default=False) # Bloqueio temporario ou permanente
    failed_attempts = Column(Integer, default=0) # Contador para gatilho de seguranca
    
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="owner")
    logs = relationship("AccessLog", back_populates="user") # Relacionamento com o sistema de log

# ### INICIO DO SISTEMA DE LOG DE AUDITORIA ###
class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    
    # Detalhes da atividade para rastreabilidade
    activity = Column(String, nullable=False) # Ex: 'LOGIN_SUCCESS', 'ACCESS_DENIED_AREA', 'FILE_UPLOAD_ATTEMPT'
    details = Column(Text, nullable=True)     # Descricao detalhada do erro ou acao
    status = Column(String, default="INFO")   # Niveis: INFO, WARNING, ERROR, CRITICAL
    ip_address = Column(String, nullable=True) # Para auditoria de origem
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="logs")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, nullable=True)
    area = Column(String, nullable=False, default="Geral")
    history_json = Column(JSON, default=list)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    
    # ### ATENCAO: O CONTEUDO AQUI SERA ARMAZENADO CRIPTOGRAFADO ###
    content = Column(Text, nullable=False) 
    
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")