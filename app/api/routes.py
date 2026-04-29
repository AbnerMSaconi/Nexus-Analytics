from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import os
import logging
from fastapi import UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from app.utils.websocket_manager import manager
import shutil
from pathlib import Path
from quebrapdf import quebrar_arquivo_unico

# Imports do Projeto
from app.api import schemas, models
from app.core import security
from app.core.database import get_db, SessionLocal
from app.core.rag import get_rag_chain_async, atualizar_base_de_conhecimento_async
from app.core.config import settings
from app.core.security import get_current_user, encrypt_message, decrypt_message
from app.utils.performance import PerformanceMonitor

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. SISTEMA DE LOG E GATILHOS DE SEGURANÇA (AUDITORIA)
# ==============================================================================

def log_activity(db: Session, user: models.User, activity: str, status_log: str, details: str = None):
    """
    Registra logs no banco e dispara gatilhos de bloqueio se houver falhas repetidas.
    """
    try:
        # Cria o log
        new_log = models.AccessLog(
            user_id=user.id,
            activity=activity,
            status=status_log,
            details=details
        )
        db.add(new_log)
        
        # Verifica Gatilho de Bloqueio (5 falhas consecutivas)
        if status_log in ["ERROR", "CRITICAL", "ACCESS_DENIED"]:
            if hasattr(user, 'failed_attempts'):
                user.failed_attempts += 1
                if user.failed_attempts >= 5:
                    user.is_blocked = True
                    db.add(models.AccessLog(
                        user_id=user.id,
                        activity="AUTO_BLOCK_TRIGGERED",
                        status="CRITICAL",
                        details="Usuario bloqueado automaticamente apos 5 atividades suspeitas."
                    ))
        elif activity == "LOGIN_SUCCESS":
            # Reseta falhas ao logar com sucesso
            if hasattr(user, 'failed_attempts'):
                user.failed_attempts = 0
                
        db.commit()
    except Exception as e:
        logger.error(f"Falha ao registrar log de auditoria: {e}")

# ==============================================================================
# 2. ROTAS DE AUTENTICAÇÃO E PERFIL
# ==============================================================================

@router.post("/signup", response_model=schemas.Token)
async def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário.
    """
    user = db.query(models.User).filter(models.User.external_id == user_in.external_id).first()
    if user:
        raise HTTPException(status_code=400, detail="ID/Usuário já cadastrado.")
    
    hashed_pw = security.get_password_hash(user_in.password)
    
    new_user = models.User(
        external_id=user_in.external_id,
        full_name=user_in.full_name,
        password_hash=hashed_pw,
        role=user_in.role,
        course=user_in.course
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    log_activity(db, new_user, "USER_REGISTER", "INFO", "Novo usuário registrado.")
    
    access_token = security.create_access_token(
        data={"sub": new_user.external_id, "role": new_user.role, "course": new_user.course}
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "id": new_user.id,
        "role": new_user.role,
        "course": new_user.course
    }

@router.post("/login", response_model=schemas.Token)
async def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.external_id == user_in.external_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    # Verificação de Bloqueio
    if user.is_blocked:
        log_activity(db, user, "LOGIN_ATTEMPT_BLOCKED", "WARNING", "Tentativa de acesso em conta bloqueada")
        raise HTTPException(status_code=403, detail="Conta bloqueada. Contate o administrador.")

    # Verificação de Senha
    if not security.verify_password(user_in.password, user.password_hash):
        log_activity(db, user, "LOGIN_FAILED", "ERROR", "Senha incorreta")
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    
    # Sucesso
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
# 3. ROTAS DE DADOS E GESTÃO
# ==============================================================================

@router.get("/knowledge-areas")
async def get_knowledge_areas():
    """
    Retorna a estrutura de pastas e documentos (usado pelo DocumentManager).
    """
    try:
        base = settings.vectorstore_path
        if not os.path.exists(base): return {"data": []}
        
        result = []
        dirs = [d for d in os.listdir(base) if d.startswith("index_")]
        
        for d in sorted(dirs):
            area_name = d.replace("index_", "").replace("_", " ").capitalize()
            manifest_path = os.path.join(base, d, "manifest.json")
            documents = []
            
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for filename, meta in data.items():
                            if isinstance(meta, dict):
                                documents.append({
                                    "filename": filename,
                                    "title": meta.get("title", filename),
                                    "pages": meta.get("pages_indexed", 0),
                                    "updated": meta.get("last_updated", "")
                                })
                except Exception as e:
                    logger.error(f"Erro lendo manifesto: {e}")
            
            result.append({"area": area_name, "documents": documents})
            
        return {"data": result}
    except Exception as e:
        logger.error(f"Erro ao listar áreas: {e}")
        return {"data": []}

@router.post("/ingest")
async def ingest_files(background_tasks: BackgroundTasks, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Gatilho manual para processamento de documentos (Restrito) em segundo plano.
    """
    if current_user.role == "aluno":
        log_activity(db, current_user, "ACCESS_DENIED_INGEST", "WARNING", "Aluno tentou ingerir documentos.")
        raise HTTPException(status_code=403, detail="Permissão negada.")
    
    log_activity(db, current_user, "INGEST_START", "INFO", "Usuario iniciou ingestao.")
    
    background_tasks.add_task(atualizar_base_de_conhecimento_async)
    return {"status": "processing", "message": "A ingestão global foi iniciada em segundo plano."}
    
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Mantém a conexão aberta
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)

@router.post("/admin/upload")
async def upload_files_to_area(
    background_tasks: BackgroundTasks,
    area: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Recebe arquivos, fatia automaticamente se tiverem sumário, e processa para a área específica em segundo plano.
    """
    # 1. Permissões
    if current_user.role not in ["administrador", "professor", "coordenador"]:
        raise HTTPException(status_code=403, detail="Sem permissão para upload.")

    # 2. Sanitiza o nome da área
    area_clean = area.lower().strip().replace(" ", "_")
    base_dir = Path(settings.pdf_path) / area_clean
    base_dir.mkdir(parents=True, exist_ok=True)
    
    arquivos_finais_para_vetorizar = []
    
    # 3. Salva os arquivos e tenta fatiar
    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in ['.pdf', '.docx', '.txt']:
            logger.warning(f"Formato não suportado ignorado: {filename}")
            continue

        file_path = base_dir / filename
        
        # Salva o arquivo bruto no disco
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        if ext == '.pdf':
            # === A MÁGICA ACONTECE APENAS PARA PDF ===
            partes_geradas = quebrar_arquivo_unico(str(file_path))
            arquivos_finais_para_vetorizar.extend(partes_geradas)
        else:
            # DOCX e TXT vão direto
            arquivos_finais_para_vetorizar.append(str(file_path))
        
    log_activity(db, current_user, "FILE_UPLOAD", "INFO", f"Enviou {len(files)} arquivos e gerou {len(arquivos_finais_para_vetorizar)} partes na área {area}")
    
    # 4. Chama o pipeline de vetorização específico em background (agora com user_id para notificação)
    from app.core.rag import processar_area_especifica_async
    background_tasks.add_task(processar_area_especifica_async, area_clean, arquivos_finais_para_vetorizar, str(current_user.id))
    
    return {
        "status": "processing", 
        "message": f"{len(files)} arquivo(s) recebido(s). O processamento de {len(arquivos_finais_para_vetorizar)} partes foi iniciado em segundo plano."
    }
# ==============================================================================
# 4. CHAT E CONVERSAS (SECURE & ENCRYPTED)
# ==============================================================================

@router.get("/conversations")
async def get_conversations(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Conversation).filter(
        models.Conversation.user_id == current_user.id
    ).order_by(models.Conversation.updated_at.desc()).all()

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    db.delete(conversation)
    db.commit()
    return {"status": "success"}

@router.post("/chat")
async def chat(request: Request, body: schemas.ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # 2. RBAC: Restrição de Área por Curso (BLINDADO)
    role_usuario = (current_user.role or "").lower().strip()
    
    if role_usuario in ["aluno", "professor"]:
        area_solicitada = (body.area or "geral").lower().strip()
        curso_usuario = (current_user.course or "").lower().strip()
        
        # 1. Todo aluno/professor tem acesso à base 'Geral'
        areas_permitidas = ["geral"]
        
        # 2. Se o usuário tiver um curso cadastrado, adicionamos à lista de permissões
        if curso_usuario:
            areas_permitidas.append(curso_usuario)
            
            # 3. Regra de Engenharias e Tecnologias
            if "engenharia" in curso_usuario or "tecnologia" in curso_usuario:
                areas_permitidas.extend(["engenharia", "engenharias", "tecnologia", "tecnologias"])
        
        # 4. Verifica se o que ele pediu está dentro do que ele pode acessar
        acesso_concedido = False
        area_solicitada_clean = area_solicitada.lower().strip().replace(" ", "_")
        
        for permitida in areas_permitidas:
            permitida_clean = permitida.lower().strip().replace(" ", "_")
            # Match exato ou match de categoria (ex: engenharia_civil contém engenharia)
            if permitida_clean == area_solicitada_clean or permitida_clean in area_solicitada_clean:
                acesso_concedido = True
                break
                
        # 5. Se não passou na validação, BLOQUEIA
        if not acesso_concedido:
            log_activity(db, current_user, "ACCESS_DENIED_AREA", "WARNING", f"{current_user.role} de {curso_usuario} tentou acessar {body.area}")
            
            # Mensagem amigável de erro
            curso_display = current_user.course if current_user.course else "Geral (Nenhum curso cadastrado)"
            msg = f"Acesso Negado: {current_user.role.capitalize()}s de {curso_display} não têm permissão para acessar a base de {body.area}."
            
            return StreamingResponse(iter([f'data: {json.dumps({"type": "error", "content": msg})}\n\n']))

    log_activity(db, current_user, "CHAT_START", "INFO", f"Chat na area {body.area}")

    from app.core.rag import get_rag_chain_async
    rag_chain = await get_rag_chain_async(body.area)
    
    if not rag_chain: 
        msg = f"A base de conhecimento '{body.area}' ainda não foi indexada. Por favor, adicione documentos e processe-os no painel administrativo."
        return StreamingResponse(iter([f'data: {json.dumps({"type": "error", "content": msg})}\n\n']))

    # 3. Cria Conversa e Mensagem
    new_conv = models.Conversation(
        user_id=current_user.id,
        title=body.message[:40] + "...",
        area=body.area or "Geral"
    )
    db.add(new_conv)
    db.commit()
    
    encrypted_input = encrypt_message(body.message)
    db.add(models.Message(conversation_id=new_conv.id, role="user", content=encrypted_input))
    db.commit()

    async def event_stream():
        async with PerformanceMonitor.async_timer("Geração de Resposta Total (End-to-End)"):
            full_answer = ""
            source_documents = []
            try:
                yield f"data: {json.dumps({'type': 'start'})}\n\n"
                
                async for chunk in rag_chain.astream({"question": body.message, "chat_history": []}):
                    if "answer" in chunk:
                        token = chunk["answer"]
                        full_answer += token
                        yield f"data: {json.dumps({'type': 'chunk', 'content': token})}\n\n"
                    if "source_documents" in chunk:
                        source_documents = chunk["source_documents"]

                if source_documents:
                    unique_sources = {}
                    for d in source_documents:
                        full_path = d.metadata.get("source", "")
                        filename = os.path.basename(full_path)
                        try:
                            relative_path = os.path.relpath(full_path, settings.pdf_path)
                        except:
                            relative_path = filename

                        if filename not in unique_sources:
                            unique_sources[filename] = {
                                "filename": filename,
                                "filepath": relative_path,
                                "topic": d.metadata.get("topic", "Documento")
                            }
                    yield f"data: {json.dumps({'type': 'sources', 'content': list(unique_sources.values())}, ensure_ascii=False)}\n\n"

                with SessionLocal() as db2:
                    encrypted_output = encrypt_message(full_answer)
                    db2.add(models.Message(conversation_id=new_conv.id, role="ai", content=encrypted_output))
                    db2.commit()
                
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

            except Exception as e:
                logger.error(f"Erro no chat: {e}")
                with SessionLocal() as db_err:
                    u = db_err.query(models.User).filter(models.User.id == current_user.id).first()
                    log_activity(db_err, u, "SYSTEM_ERROR", "ERROR", str(e))
                yield f"data: {json.dumps({'type': 'error', 'content': 'Erro interno.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ==============================================================================
# 5. ROTAS DE ADMINISTRADOR (COMPLETAS)
# ==============================================================================

@router.get("/admin/users", response_model=List[schemas.UserResponse])
async def list_users_admin(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    return db.query(models.User).all()

@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Permissão
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    # 2. Busca Usuário
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # 3. Proteção Auto-Exclusão
    if user_to_delete.id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")

    # 4. Exclusão
    try:
        # Remove logs e conversas associadas (se não tiver cascade no banco)
        db.query(models.AccessLog).filter(models.AccessLog.user_id == user_id).delete()
        db.query(models.Conversation).filter(models.Conversation.user_id == user_id).delete()
        
        db.delete(user_to_delete)
        db.commit()
        
        log_activity(db, current_user, "ADMIN_DELETE_USER", "WARNING", f"Excluiu usuário {user_to_delete.external_id}")
        return {"status": "success", "message": "Usuário excluído com sucesso."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir: {str(e)}")

@router.put("/admin/users/{user_id}/role")
async def update_user_role(
    user_id: str, 
    role_data: schemas.UserRoleUpdate, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(404, detail="Usuário não encontrado.")
    
    # Proteção: não deixar admin se rebaixar
    if user_target.id == current_user.id and role_data.role != "administrador":
         raise HTTPException(400, detail="Você não pode alterar seu próprio cargo de administrador.")

    old_role = user_target.role
    user_target.role = role_data.role
    db.commit()
    
    log_activity(db, current_user, "ADMIN_ROLE_CHANGE", "INFO", f"Alterou {user_target.external_id} de {old_role} para {role_data.role}")
    return {"status": "success", "message": f"Cargo alterado para {role_data.role}"}

@router.post("/admin/unblock/{user_id}")
async def unblock_user(user_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
        
    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(404, "Usuário não encontrado")
        
    user_target.is_blocked = False
    if hasattr(user_target, 'failed_attempts'):
        user_target.failed_attempts = 0
        
    db.commit()
    log_activity(db, current_user, "ADMIN_UNBLOCK", "INFO", f"Desbloqueou usuário {user_target.external_id}")
    return {"message": "Usuário desbloqueado"}

@router.put("/admin/users/{user_id}")
async def update_user_details(
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
    
    # Valida e atualiza ID/Login
    if user_data.external_id and user_data.external_id != user_target.external_id:
        existing = db.query(models.User).filter(models.User.external_id == user_data.external_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Este ID/Login já está em uso por outro usuário.")
        user_target.external_id = user_data.external_id

    # Atualiza demais campos
    if user_data.full_name is not None:
        user_target.full_name = user_data.full_name
        
    if user_data.role:
        if user_target.id == current_user.id and user_data.role != "administrador":
             raise HTTPException(status_code=400, detail="Você não pode alterar seu próprio cargo de administrador.")
        user_target.role = user_data.role
        
    if user_data.course is not None:
        user_target.course = user_data.course
        
    # Reset de senha
    if user_data.password:
        user_target.password_hash = security.get_password_hash(user_data.password)

    try:
        db.commit()
        log_activity(db, current_user, "ADMIN_UPDATE_USER", "INFO", f"Atualizou o cadastro do usuário {user_target.external_id}")
        return {"status": "success", "message": "Usuário atualizado com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {str(e)}")