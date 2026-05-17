from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
import logging
import httpx as _httpx
import subprocess as _subprocess

from app.api import schemas, models
from app.core import security
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.utils.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. AUDITORIA
# ==============================================================================

def log_activity(db: Session, user: models.User, activity: str, status_log: str, details: str = None):
    try:
        new_log = models.AccessLog(
            user_id=user.id,
            activity=activity,
            status=status_log,
            details=details
        )
        db.add(new_log)

        if status_log in ["ERROR", "CRITICAL", "ACCESS_DENIED"]:
            if hasattr(user, 'failed_attempts'):
                user.failed_attempts += 1
                if user.failed_attempts >= 5:
                    user.is_blocked = True
                    db.add(models.AccessLog(
                        user_id=user.id,
                        activity="AUTO_BLOCK_TRIGGERED",
                        status="CRITICAL",
                        details="Usuário bloqueado automaticamente após 5 tentativas suspeitas."
                    ))
        elif activity == "LOGIN_SUCCESS":
            if hasattr(user, 'failed_attempts'):
                user.failed_attempts = 0

        db.commit()
    except Exception as e:
        logger.error(f"Falha ao registrar log: {e}")

# ==============================================================================
# 2. AUTENTICAÇÃO
# ==============================================================================

@router.post("/login", response_model=schemas.Token)
async def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.external_id == user_in.external_id.lower().strip()
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    if user.is_blocked:
        log_activity(db, user, "LOGIN_ATTEMPT_BLOCKED", "WARNING", "Tentativa em conta bloqueada")
        raise HTTPException(status_code=403, detail="Conta bloqueada. Contate o administrador.")

    if not security.verify_password(user_in.password, user.password_hash):
        log_activity(db, user, "LOGIN_FAILED", "ERROR", "Senha incorreta")
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    log_activity(db, user, "LOGIN_SUCCESS", "INFO", "Login realizado com sucesso")

    access_token = security.create_access_token(
        data={"sub": user.external_id, "role": user.role, "course": user.course}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "id": user.id,
        "role": user.role,
        "course": user.course
    }

@router.get("/me")
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.external_id,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "course": current_user.course
    }

# ==============================================================================
# 3. WEBSOCKET (CONTADOR ONLINE)
# ==============================================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    try:
        await manager.connect(user_id, websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"Erro WebSocket para {user_id}: {e}")
        try:
            await manager.disconnect(user_id, websocket)
        except:
            pass

# ==============================================================================
# 4. ADMINISTRAÇÃO DE USUÁRIOS
# ==============================================================================

@router.get("/admin/users", response_model=List[schemas.UserResponse])
async def list_users(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    return db.query(models.User).all()


@router.post("/admin/users", response_model=schemas.UserResponse)
async def create_user(
    user_in: schemas.UserCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    if db.query(models.User).filter(models.User.external_id == user_in.external_id).first():
        raise HTTPException(status_code=400, detail="ID/Usuário já cadastrado.")

    new_user = models.User(
        external_id=user_in.external_id.lower().strip(),
        full_name=user_in.full_name,
        password_hash=security.get_password_hash(user_in.password),
        role=user_in.role.lower().strip(),
        course=user_in.course.lower().strip() if user_in.course else None
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_activity(db, current_user, "ADMIN_CREATE_USER", "INFO", f"Criou: {new_user.external_id}")
    return new_user


@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if user_target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")

    try:
        db.query(models.AccessLog).filter(models.AccessLog.user_id == user_id).delete()
        db.query(models.Conversation).filter(models.Conversation.user_id == user_id).delete()
        db.delete(user_target)
        db.commit()
        log_activity(db, current_user, "ADMIN_DELETE_USER", "WARNING", f"Excluiu: {user_target.external_id}")
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/users/{user_id}/role")
async def update_role(
    user_id: str,
    role_data: schemas.UserRoleUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if user_target.id == current_user.id and role_data.role != "administrador":
        raise HTTPException(status_code=400, detail="Você não pode rebaixar seu próprio cargo.")

    old_role = user_target.role
    user_target.role = role_data.role
    db.commit()
    log_activity(db, current_user, "ADMIN_ROLE_CHANGE", "INFO",
                 f"{user_target.external_id}: {old_role} → {role_data.role}")
    return {"status": "success"}


@router.post("/admin/unblock/{user_id}")
async def unblock_user(
    user_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    user_target.is_blocked = False
    if hasattr(user_target, 'failed_attempts'):
        user_target.failed_attempts = 0

    db.commit()
    log_activity(db, current_user, "ADMIN_UNBLOCK", "INFO", f"Desbloqueou: {user_target.external_id}")
    return {"message": "Usuário desbloqueado"}


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if user_data.external_id and user_data.external_id.lower().strip() != user_target.external_id:
        new_id = user_data.external_id.lower().strip()
        if db.query(models.User).filter(models.User.external_id == new_id).first():
            raise HTTPException(status_code=400, detail="Este login já está em uso.")
        user_target.external_id = new_id

    if user_data.full_name is not None:
        user_target.full_name = user_data.full_name

    if user_data.role:
        new_role = user_data.role.lower().strip()
        if user_target.id == current_user.id and new_role != "administrador":
            raise HTTPException(status_code=400, detail="Você não pode rebaixar seu próprio cargo.")
        user_target.role = new_role

    if user_data.course is not None:
        user_target.course = user_data.course.lower().strip() if user_data.course else None

    if user_data.password:
        user_target.password_hash = security.get_password_hash(user_data.password)

    try:
        db.commit()
        log_activity(db, current_user, "ADMIN_UPDATE_USER", "INFO",
                     f"Atualizou: {user_target.external_id}")
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# 5. STATUS DO SISTEMA
# ==============================================================================

@router.get("/system/status")
async def system_status():
    result = {
        "llm": {"ok": False, "model": None, "n_ctx": None, "slots": None},
        "embedding": {"ok": False, "model": None},
        "gpu": [],
    }

    async with _httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{str(settings.LLM_BASE_URL).rstrip('/v1')}/props")
            if r.status_code == 200:
                props = r.json()
                result["llm"]["ok"] = True
                result["llm"]["model"] = props.get("model_path", "?")
                result["llm"]["n_ctx"] = props.get("default_generation_settings", {}).get("n_ctx")
        except Exception:
            pass

        try:
            r = await client.get(f"{str(settings.LLM_BASE_URL).rstrip('/v1')}/slots")
            if r.status_code == 200:
                slots = r.json()
                result["llm"]["slots"] = {
                    "total": len(slots),
                    "processando": sum(1 for s in slots if s.get("state") == 1)
                }
        except Exception:
            pass

        try:
            base_emb = str(settings.EMBEDDING_API_URL).replace("/embedding", "")
            r = await client.get(f"{base_emb}/props")
            if r.status_code == 200:
                props = r.json()
                result["embedding"]["ok"] = True
                result["embedding"]["model"] = props.get("model_path", "?")
        except Exception:
            pass

    try:
        out = _subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            timeout=5,
        ).decode()
        for line in out.strip().splitlines():
            idx, name, util, mem_used, mem_total, temp = [x.strip() for x in line.split(",")]
            result["gpu"].append({
                "index": int(idx), "name": name,
                "utilizacao_pct": int(util),
                "memoria_usada_mb": int(mem_used),
                "memoria_total_mb": int(mem_total),
                "temperatura_c": int(temp),
            })
    except Exception:
        pass

    return result
