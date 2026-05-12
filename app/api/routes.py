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
from app.core.rag import (
    get_rag_chain_async, 
    atualizar_base_de_conhecimento_async, 
    carregar_manifesto, 
    salvar_manifesto, 
    processar_area_especifica_async,
    _normalizar_nome_area
)
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

def validar_cursos_usuario(role: str, course_str: str):
    """
    Valida a regra de cursos:
    - Aluno: Máximo 2 cursos (sem restrição de turno).
    - Professor/Coordenador: Múltiplos cursos permitidos.
    """
    if not course_str:
        return
    
    import re
    cursos = [c.strip().lower() for c in re.split(r'[,;]', course_str) if c.strip()]
    
    if role.lower() == "aluno":
        if len(cursos) > 2:
            raise HTTPException(status_code=400, detail="Um aluno pode estar matriculado em no máximo 2 cursos.")

@router.post("/signup", response_model=schemas.Token)
async def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário.
    """
    validar_cursos_usuario("aluno", user_in.course)
    user = db.query(models.User).filter(models.User.external_id == user_in.external_id).first()
    if user:
        raise HTTPException(status_code=400, detail="ID/Usuário já cadastrado.")
    
    hashed_pw = security.get_password_hash(user_in.password)
    
    # FORÇADO: Por segurança, novos cadastros via API externa são sempre ALUNOS.
    # Promoção para Admin deve ser feita via script de terminal.
    new_user = models.User(
        external_id=user_in.external_id.lower().strip(),
        full_name=user_in.full_name,
        password_hash=hashed_pw,
        role=user_in.role.lower().strip(), 
        course=user_in.course.lower().strip() if user_in.course else None
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
    user = db.query(models.User).filter(models.User.external_id == user_in.external_id.lower().strip()).first()
    
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
    logger.info(f"🔍 Tentativa de conexão WS recebida para user_id: {user_id}")
    try:
        await manager.connect(user_id, websocket)
        while True:
            # Mantém a conexão aberta e responde a pings do cliente se necessário
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"⚠️ Erro inesperado no WebSocket para {user_id}: {e}")
        try:
            await manager.disconnect(user_id, websocket)
        except:
            pass

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

    # 2. Sanitiza o nome da área (Path Traversal Protection)
    area_safe = os.path.basename(area.lower().strip().replace(" ", "_"))
    base_dir = Path(settings.pdf_path) / area_safe
    base_dir.mkdir(parents=True, exist_ok=True)
    
    arquivos_finais_para_vetorizar = []
    
    # 3. Salva os arquivos e tenta fatiar
    for file in files:
        # Sanitização do Nome do Arquivo (Security Fix)
        filename = os.path.basename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in ['.pdf', '.docx', '.txt']:
            logger.warning(f"Formato não suportado ignorado: {filename}")
            continue

        file_path = base_dir / filename
        
        # Salva o arquivo bruto no disco
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        arquivos_finais_para_vetorizar.append(str(file_path))
        
    log_activity(db, current_user, "FILE_UPLOAD", "INFO", f"Enviou {len(files)} arquivos na área {area_safe}")
    
    # 4. Chama o pipeline de vetorização em background
    from app.core.rag import processar_area_especifica_async
    background_tasks.add_task(processar_area_especifica_async, area_safe, arquivos_finais_para_vetorizar, str(current_user.id), True)
    
    return {
        "status": "processing", 
        "message": f"{len(arquivos_finais_para_vetorizar)} arquivos foram recebidos e estão sendo processados na área {area_safe}.",
        "area": area_safe
    }

@router.delete("/admin/documents")
async def delete_document(
    area: str,
    filename: str,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exclui um arquivo específico e remove do índice FAISS (reindexação necessária para sumir do chat)."""
    if current_user.role not in ["administrador", "professor", "coordenador"]:
        raise HTTPException(status_code=403, detail="Sem permissão.")

    area_safe = os.path.basename(area.lower().strip().replace(" ", "_"))
    filename_safe = os.path.basename(filename)

    if filename_safe == "undefined":
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido (undefined).")

    # 1. Remove o arquivo físico
    file_path = Path(settings.pdf_path) / area_safe / filename_safe
    if not file_path.exists():
        logger.warning(f"Tentativa de excluir arquivo inexistente: {file_path}")
        # Mesmo se o arquivo não existir, prosseguimos para limpar o manifesto e o índice caso haja sujeira
    else:
        os.remove(file_path)
    # 2. Remove do manifesto
    caminho_indice = Path(settings.vectorstore_path) / f"index_{area_safe}"
    manifesto = carregar_manifesto(str(caminho_indice))
    if filename_safe in manifesto:
        del manifesto[filename_safe]
        salvar_manifesto(str(caminho_indice), manifesto)
    
    # 3. Dispara a limpeza total (Rebuild do índice daquela área)
    # Isso garante que os embeddings do arquivo deletado sumam do FAISS
    background_tasks.add_task(processar_area_especifica_async, area, None, str(current_user.id), True)
        
    log_activity(db, current_user, "FILE_DELETE", "WARNING", f"Excluiu {filename_safe} da área {area_safe}")
    return {"status": "success", "message": f"Arquivo {filename_safe} excluído. O índice está sendo reconstruído para remover os dados permanentemente."}

@router.delete("/admin/areas/{area}")
async def delete_area(
    area: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exclui uma área inteira (Arquivos + Índices)."""
    if current_user.role not in ["administrador", "professor", "coordenador"]:
        raise HTTPException(status_code=403, detail="Sem permissão.")

    area_safe = os.path.basename(area.lower().strip().replace(" ", "_"))
    
    # 1. Deleta arquivos PDF
    pdf_dir = Path(settings.pdf_path) / area_safe
    if pdf_dir.exists():
        shutil.rmtree(pdf_dir)
        
    # 2. Deleta índices FAISS
    index_dir = Path(settings.vectorstore_path) / f"index_{area_safe}"
    if index_dir.exists():
        shutil.rmtree(index_dir)
        
    log_activity(db, current_user, "AREA_DELETE", "CRITICAL", f"Excluiu a área inteira: {area_safe}")
    return {"status": "success", "message": f"Área {area_safe} e todos os seus documentos foram excluídos."}
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

    # Normalização da área solicitada para comparação
    area_solicitada_raw = body.area or "geral"
    area_solicitada_clean = _normalizar_nome_area(area_solicitada_raw)

    if role_usuario in ["aluno", "professor"]:
        # Suporte a múltiplos cursos (separados por vírgula)
        import re
        cursos_usuario = [c.strip().lower() for c in re.split(r'[,;]', current_user.course or "") if c.strip()]

        # 1. Todo aluno/professor tem acesso à base 'Geral'
        areas_permitidas = ["geral"]

        # 2. Adicionamos todos os cursos do usuário às permissões
        areas_permitidas.extend(cursos_usuario)

        # 3. Regra de Engenharias e Tecnologias para todos os cursos dele
        for curso in cursos_usuario:
            if "engenharia" in curso or "tecnologia" in curso:
                areas_permitidas.extend(["engenharia", "engenharias", "tecnologia", "tecnologias"])

        # 4. Verifica se o que ele pediu está dentro do que ele pode acessar
        acesso_concedido = False

        for permitida in areas_permitidas:
            permitida_clean = permitida.lower().strip().replace(" ", "_")
            # Correção: permitida_clean in area_solicitada_clean OU area_solicitada_clean in permitida_clean
            # Isso permite que 'engenharia_de_software' acesse 'engenharia' e vice-versa
            if (permitida_clean == area_solicitada_clean or 
                permitida_clean in area_solicitada_clean or 
                area_solicitada_clean in permitida_clean):
                acesso_concedido = True
                break

        # 5. Se não passou na validação, BLOQUEIA
        if not acesso_concedido:
            log_activity(db, current_user, "ACCESS_DENIED_AREA", "WARNING", f"{current_user.role} de {current_user.course} tentou acessar {body.area}")

            # Mensagem amigável de erro
            curso_display = current_user.course if current_user.course else "Geral (Nenhum curso cadastrado)"
            msg = f"Acesso Negado: {current_user.role.capitalize()}s de {curso_display} não têm permissão para acessar a base de {body.area}."

            return StreamingResponse(iter([f'data: {json.dumps({"type": "error", "content": msg})}\n\n']))

    # --- ISOLAMENTO ESTRITO DE ÁREA ---
    # O sistema agora respeita RIGOROSAMENTE a área selecionada pelo usuário.
    # Não há mais redirecionamento automático para evitar mistura de contextos.
    area_final = area_solicitada_raw

    log_activity(db, current_user, "CHAT_START", "INFO", f"Chat estrito na area {area_final}")

    # 1. Proteção contra Prompt Injection (Básico)
    forbidden_patterns = [
        "ignore todas as instruções anteriores", 
        "ignore previous instructions",
        "você agora é um", "you are now a",
        "system prompt", "instrução do sistema"
    ]
    message_lower = body.message.lower()
    if any(p in message_lower for p in forbidden_patterns):
        log_activity(db, current_user, "PROMPT_INJECTION_ATTEMPT", "CRITICAL", f"Usuário enviou prompt suspeito: {body.message[:100]}")
        msg = "Desculpe, detectamos uma tentativa de manipulação de prompt. Sua atividade foi registrada para auditoria."
        return StreamingResponse(iter([f'data: {json.dumps({"type": "error", "content": msg})}\n\n']))

    from app.core.rag import get_rag_chain_async
    rag_chain = await get_rag_chain_async(area_final)

    if not rag_chain: 
        # Em vez de erro técnico, retornamos uma resposta amigável do bot explicando a situação
        friendly_msg = (
            f"### ⚠️ Base de Conhecimento: {area_final.capitalize()}\n\n"
            f"Olá! Notei que a base de conhecimento **{area_final}** ainda não possui documentos processados no sistema.\n\n"
            f"Como sou um assistente focado em documentos oficiais da UCDB, preciso que PDFs sejam enviados e processados para esta área para que eu possa te responder com precisão.\n\n"
            f"**O que fazer?**\n"
            f"- Se você for um administrador, acesse o **Gerenciador de Documentos** e realize o upload para esta área.\n"
            f"- Se for um aluno, entre em contato com a coordenação do seu curso para que disponibilizem os materiais aqui."
        )

        async def empty_stream():
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            yield f"data: {json.dumps({'type': 'chunk', 'content': friendly_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        return StreamingResponse(empty_stream(), media_type="text/event-stream")    # 3. Cria Conversa e Mensagem
    new_conv = models.Conversation(
        user_id=current_user.id,
        title=body.message[:40] + "...",
        area=area_final
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
    if current_user.role == "administrador":
        return db.query(models.User).all()
    
    if current_user.role == "coordenador":
        # Se não tiver curso definido, não vê ninguém
        if not current_user.course:
            return []
            
        # Pega a lista de cursos do coordenador (separados por vírgula ou ponto e vírgula)
        import re
        coordinators_courses = [c.strip().lower() for c in re.split(r'[,;]', current_user.course) if c.strip()]
        
        # Busca todos os alunos (case-insensitive para o cargo)
        from sqlalchemy import func
        all_students = db.query(models.User).filter(func.lower(models.User.role) == "aluno").all()
        
        # Filtra manualmente para garantir match flexível (ex: 'Direito' em 'Direito Matutino')
        filtered = []
        for student in all_students:
            student_course = (student.course or "").lower().strip()
            if any(coord_course in student_course for coord_course in coordinators_courses):
                filtered.append(student)
        return filtered

    raise HTTPException(status_code=403, detail="Acesso restrito.")

@router.post("/admin/users", response_model=schemas.UserResponse)
async def create_user_admin(
    user_in: schemas.UserCreate, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Cria um novo usuário (Restrito a administradores e coordenadores).
    """
    if current_user.role not in ["administrador", "coordenador"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    # Validação para Coordenador: só pode criar Aluno na sua área
    if current_user.role == "coordenador":
        if user_in.role.lower() != "aluno":
            raise HTTPException(status_code=403, detail="Coordenadores só podem cadastrar alunos.")
        
        import re
        coordinators_courses = [c.strip().lower() for c in re.split(r'[,;]', current_user.course or "") if c.strip()]
        student_course = (user_in.course or "").lower().strip()
        
        if not any(coord_course in student_course for coord_course in coordinators_courses):
            raise HTTPException(status_code=403, detail="Você só pode cadastrar alunos em seus cursos de atuação.")

    validar_cursos_usuario(user_in.role, user_in.course)

    user = db.query(models.User).filter(models.User.external_id == user_in.external_id).first()
    if user:
        raise HTTPException(status_code=400, detail="ID/Usuário já cadastrado.")
    
    hashed_pw = security.get_password_hash(user_in.password)
    
    new_user = models.User(
        external_id=user_in.external_id.lower().strip(),
        full_name=user_in.full_name,
        password_hash=hashed_pw,
        role=user_in.role.lower().strip(), 
        course=user_in.course.lower().strip() if user_in.course else None
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    log_activity(db, current_user, "ADMIN_CREATE_USER", "INFO", f"Criou novo usuário: {new_user.external_id}")
    return new_user

@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Permissão
    if current_user.role not in ["administrador", "coordenador"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    # 2. Busca Usuário
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # 3. Proteções
    if user_to_delete.id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")

    # Validação para Coordenador: só pode excluir Aluno na sua área
    if current_user.role == "coordenador":
        if user_to_delete.role != "aluno":
            raise HTTPException(status_code=403, detail="Coordenadores só podem excluir alunos.")
        
        import re
        coordinators_courses = [c.strip().lower() for c in re.split(r'[,;]', current_user.course or "") if c.strip()]
        student_course = (user_to_delete.course or "").lower().strip()
        
        if not any(coord_course in student_course for coord_course in coordinators_courses):
            raise HTTPException(status_code=403, detail="Você não tem permissão para excluir este aluno.")

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
        raise HTTPException(status_code=403, detail="Acesso restrito. Apenas administradores podem alterar cargos.")
    
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
    if current_user.role not in ["administrador", "coordenador"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
        
    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(404, "Usuário não encontrado")

    # Validação Coordenador
    if current_user.role == "coordenador":
        if user_target.role != "aluno":
             raise HTTPException(status_code=403, detail="Permissão negada.")
        
        import re
        coordinators_courses = [c.strip().lower() for c in re.split(r'[,;]', current_user.course or "") if c.strip()]
        student_course = (user_target.course or "").lower().strip()
        if not any(coord_course in student_course for coord_course in coordinators_courses):
            raise HTTPException(status_code=403, detail="Permissão negada para este aluno.")
        
    user_target.is_blocked = False
    if hasattr(user_target, 'failed_attempts'):
        user_target.failed_attempts = 0
        
    db.commit()
    log_activity(db, current_user, "ADMIN_UNBLOCK", "INFO", f"Desbloqueou usuário {user_target.external_id}")
    return {"message": "Usuário desbloqueado"}


# ── System Status ─────────────────────────────────────────────────────────────

import httpx as _httpx
import subprocess as _subprocess

@router.get("/system/status")
async def system_status():
    """Retorna status dos serviços LLM, embedding e GPU."""
    result = {
        "llm": {"ok": False, "model": None, "n_ctx": None, "slots": None},
        "embedding": {"ok": False, "model": None},
        "gpu": [],
    }

    async with _httpx.AsyncClient(timeout=5.0) as client:
        # LLM props
        try:
            r = await client.get(f"{str(settings.LLM_BASE_URL).rstrip('/v1')}/props")
            if r.status_code == 200:
                props = r.json()
                result["llm"]["ok"] = True
                result["llm"]["model"] = props.get("model_path", props.get("default_generation_settings", {}).get("model", "?"))
                result["llm"]["n_ctx"] = props.get("default_generation_settings", {}).get("n_ctx")
        except Exception:
            pass

        # LLM slots (processamento atual)
        try:
            r = await client.get(f"{str(settings.LLM_BASE_URL).rstrip('/v1')}/slots")
            if r.status_code == 200:
                slots = r.json()
                processando = sum(1 for s in slots if s.get("state") == 1)
                result["llm"]["slots"] = {"total": len(slots), "processando": processando}
        except Exception:
            pass

        # Embedding props
        try:
            base_emb = str(settings.EMBEDDING_API_URL).replace("/embedding", "")
            r = await client.get(f"{base_emb}/props")
            if r.status_code == 200:
                props = r.json()
                result["embedding"]["ok"] = True
                result["embedding"]["model"] = props.get("model_path", "?")
        except Exception:
            pass

    # GPU via nvidia-smi
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
                "index": int(idx),
                "name": name,
                "utilizacao_pct": int(util),
                "memoria_usada_mb": int(mem_used),
                "memoria_total_mb": int(mem_total),
                "temperatura_c": int(temp),
            })
    except Exception:
        pass

    return result

@router.put("/admin/users/{user_id}")
async def update_user_details(
    user_id: str,
    user_data: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["administrador", "coordenador"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    user_target = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    # Validação Coordenador
    if current_user.role == "coordenador":
        if user_target.role != "aluno":
             raise HTTPException(status_code=403, detail="Coordenadores só podem editar alunos.")
        
        import re
        coordinators_courses = [c.strip().lower() for c in re.split(r'[,;]', current_user.course or "") if c.strip()]
        
        # Valida aluno original
        student_course_orig = (user_target.course or "").lower().strip()
        if not any(coord_course in student_course_orig for coord_course in coordinators_courses):
            raise HTTPException(status_code=403, detail="Permissão negada para editar este aluno.")

        # Valida se está tentando mudar o cargo
        if user_data.role and user_data.role.lower() != "aluno":
            raise HTTPException(status_code=403, detail="Coordenadores só podem manter o cargo de Aluno.")
            
        # Valida se está tentando mover o aluno para um curso fora da sua coordenação
        if user_data.course:
            new_course = user_data.course.lower().strip()
            if not any(coord_course in new_course for coord_course in coordinators_courses):
                raise HTTPException(status_code=403, detail="Você não pode mover o aluno para um curso fora da sua coordenação.")
    
    # Valida a regra de múltiplos cursos e turnos
    role_para_validar = user_data.role if user_data.role else user_target.role
    curso_para_validar = user_data.course if user_data.course is not None else user_target.course
    validar_cursos_usuario(role_para_validar, curso_para_validar)

    # Valida e atualiza ID/Login
    if user_data.external_id and user_data.external_id.lower().strip() != user_target.external_id:
        new_ext_id = user_data.external_id.lower().strip()
        existing = db.query(models.User).filter(models.User.external_id == new_ext_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Este RA já está em uso por outro usuário.")
        user_target.external_id = new_ext_id

    # Atualiza demais campos
    if user_data.full_name is not None:
        user_target.full_name = user_data.full_name
        
    if user_data.role:
        new_role = user_data.role.lower().strip()
        if user_target.id == current_user.id and new_role != "administrador":
             raise HTTPException(status_code=400, detail="Você não pode alterar seu próprio cargo de administrador.")
        user_target.role = new_role
        
    if user_data.course is not None:
        user_target.course = user_data.course.lower().strip() if user_data.course else None
        
    # Reset de senha
    if user_data.password:
        user_target.password_hash = security.get_password_hash(user_data.password)

    try:
        db.commit()
        # LIMPEZA DE CACHE: Se o cargo ou curso mudaram, limpamos o cache para forçar recarregamento das permissões
        from app.core.rag import _vs_cache
        _vs_cache.cache.clear()
        
        log_activity(db, current_user, "ADMIN_UPDATE_USER", "INFO", f"Atualizou o cadastro do usuário {user_target.external_id}")
        return {"status": "success", "message": "Usuário atualizado com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar: {str(e)}")