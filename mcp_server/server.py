import os
import sys
import uuid
from datetime import datetime
from typing import Optional, List

# Adiciona o diretório raiz ao path para importar os módulos do app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.api.models import User, AccessLog, Conversation

# Inicializa o FastMCP
mcp = FastMCP("UCDB-IA Maintenance Server")

# --- Ferramentas de Usuário ---

@mcp.tool()
def list_users(limit: int = 10) -> str:
    """Lista os usuários cadastrados no sistema."""
    db: Session = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).limit(limit).all()
        if not users:
            return "Nenhum usuário encontrado."
        
        result = "ID Externo | Nome | Cargo | Curso | Bloqueado\n"
        result += "-" * 60 + "\n"
        for u in users:
            result += f"{u.external_id} | {u.full_name} | {u.role} | {u.course} | {u.is_blocked}\n"
        return result
    finally:
        db.close()

@mcp.tool()
def promote_user_to_admin(external_id: str) -> str:
    """Promove um usuário para o cargo de administrador."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id).first()
        if not user:
            return f"Erro: Usuário '{external_id}' não encontrado."
        
        user.role = "administrador"
        db.commit()
        return f"Sucesso: Usuário '{external_id}' ({user.full_name}) agora é Administrador."
    except Exception as e:
        return f"Erro ao promover usuário: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def unlock_user(external_id: str) -> str:
    """Desbloqueia um usuário e reseta tentativas falhas."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id).first()
        if not user:
            return f"Erro: Usuário '{external_id}' não encontrado."
        
        user.is_blocked = False
        user.failed_attempts = 0
        db.commit()
        return f"Sucesso: Usuário '{external_id}' foi desbloqueado."
    finally:
        db.close()

# --- Ferramentas de Auditoria ---

@mcp.tool()
def get_audit_logs(limit: int = 20, status: Optional[str] = None) -> str:
    """Busca os logs de auditoria mais recentes."""
    db: Session = SessionLocal()
    try:
        query = db.query(AccessLog).join(User, isouter=True)
        if status:
            query = query.filter(AccessLog.status == status.upper())
        
        logs = query.order_by(AccessLog.timestamp.desc()).limit(limit).all()
        
        if not logs:
            return "Nenhum log encontrado."
        
        result = "Data | Usuário | Atividade | Status | Detalhes\n"
        result += "-" * 80 + "\n"
        for log in logs:
            user_id = log.user.external_id if log.user else "Sistema"
            timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            result += f"{timestamp} | {user_id} | {log.activity} | {log.status} | {log.details or ''}\n"
        return result
    finally:
        db.close()

# --- Ferramentas de Sistema ---

@mcp.tool()
def system_health_check() -> str:
    """Verifica o status geral do sistema e estatísticas básicas."""
    db: Session = SessionLocal()
    try:
        user_count = db.query(User).count()
        blocked_count = db.query(User).filter(User.is_blocked == True).count()
        error_logs_24h = db.query(AccessLog).filter(
            AccessLog.status.in_(["ERROR", "CRITICAL"]),
            AccessLog.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).count()
        
        status = "🟢 SAUDÁVEL" if error_logs_24h < 5 else "🟡 ALERTA"
        if error_logs_24h > 20: status = "🔴 CRÍTICO"

        return (
            f"Status Geral: {status}\n"
            f"Total de Usuários: {user_count}\n"
            f"Usuários Bloqueados: {blocked_count}\n"
            f"Erros nas últimas 24h: {error_logs_24h}"
        )
    finally:
        db.close()

if __name__ == "__main__":
    mcp.run()
