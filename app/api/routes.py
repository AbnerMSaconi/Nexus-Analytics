from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api import schemas, models
from app.core.config import settings
from app.core import security
from app.core.security import get_current_user
from app.core.database import get_db, SessionLocal
from app.utils.logger import logger
from app.core.rag import get_rag_chain
from langchain_core.messages import HumanMessage, AIMessage
import os
import json
import uuid

router = APIRouter()

# --- AUTENTICAÇÃO ---

@router.post("/signup", response_model=schemas.Token)
async def signup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.external_id == user_in.external_id).first()
    if user:
        raise HTTPException(status_code=400, detail="ID já cadastrado.")
    
    hashed_pw = security.get_password_hash(user_in.password)
    new_user = models.User(
        external_id=user_in.external_id,
        full_name=user_in.full_name,
        password_hash=hashed_pw,
        role=user_in.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = security.create_access_token(data={"sub": new_user.external_id, "role": new_user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=schemas.Token)
async def login(user_in: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.external_id == user_in.external_id).first()
    if not user or not security.verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    
    access_token = security.create_access_token(data={"sub": user.external_id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.external_id,
        "username": current_user.full_name,
        "role": current_user.role
    }

# --- DADOS E CHAT ---

@router.get("/knowledge-areas")
async def get_knowledge_areas():
    """
    Retorna estrutura completa: Áreas -> Documentos -> Títulos IA
    Lê os arquivos manifest.json gerados pelo processo de ingestão.
    """
    try:
        base = settings.vectorstore_path
        if not os.path.exists(base): return {"data": []}
        
        result = []
        # Lista apenas diretórios que começam com 'index_'
        dirs = [d for d in os.listdir(base) if d.startswith("index_")]
        
        for d in sorted(dirs):
            # Formata o nome da área (ex: index_engenharia -> Engenharia)
            area_name = d.replace("index_", "").replace("_", " ").capitalize()
            manifest_path = os.path.join(base, d, "manifest.json")
            
            documents = []
            
            # Se existe um manifesto, lê os metadados reais (títulos da IA)
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # O manifesto é um dict: { "arquivo.pdf": { "title": "...", ... } }
                        for filename, meta in data.items():
                            if isinstance(meta, dict):
                                documents.append({
                                    "filename": filename,
                                    "title": meta.get("title", filename), # Usa o título da IA ou nome do arquivo
                                    "pages": meta.get("pages_indexed", 0),
                                    "updated": meta.get("last_updated", "")
                                })
                except Exception as e:
                    logger.error(f"Erro lendo manifesto de {area_name}: {e}")
            
            # Adiciona mesmo se não tiver documentos (para mostrar a pasta vazia)
            result.append({
                "area": area_name,
                "documents": documents
            })
            
        return {"data": result}
    except Exception as e:
        logger.error(f"Erro ao listar áreas: {e}")
        return {"data": []}

@router.get("/conversations")
async def get_conversations(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = db.query(models.Conversation).filter(
        models.Conversation.user_id == current_user.id
    ).order_by(models.Conversation.updated_at.desc()).all()
    return convs

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
    return {"status": "success", "message": "Conversa removida"}

@router.post("/chat")
async def chat(request: Request, body: schemas.ChatRequest, db: Session = Depends(get_db)):
    current_user = None
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header:
            token = auth_header.split(" ")[1]
            payload = security.jwt.decode(token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
            user_id = payload.get("sub")
            current_user = db.query(models.User).filter(models.User.external_id == user_id).first()
    except: pass

    if not body.message.strip(): return StreamingResponse(iter([]))
    
    rag_chain = get_rag_chain(body.area)
    if not rag_chain: 
        return StreamingResponse(iter(['data: {"type": "error", "content": "Índice indisponível."}\n\n']))

    conversation_id = None
    if current_user:
        new_conv = models.Conversation(
            user_id=current_user.id,
            title=body.message[:40] + "...",
            area=body.area or "Geral"
        )
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        conversation_id = new_conv.id
        
        db.add(models.Message(conversation_id=conversation_id, role="user", content=body.message))
        db.commit()

    async def event_stream():
        full_answer = ""
        source_documents = []
        try:
            history_lc = [] 
            
            yield f"data: {json.dumps({'type': 'start'})}\n\n"

            async for chunk in rag_chain.astream({"question": body.message, "chat_history": history_lc}):
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
                    except ValueError:
                        relative_path = filename

                    if filename not in unique_sources:
                        unique_sources[filename] = {
                            "filename": filename,
                            "filepath": relative_path,
                            "topic": d.metadata.get("topic", "Documento")
                        }
                yield f"data: {json.dumps({'type': 'sources', 'content': list(unique_sources.values())}, ensure_ascii=False)}\n\n"

            if conversation_id:
                with SessionLocal() as db2:
                    db2.add(models.Message(conversation_id=conversation_id, role="ai", content=full_answer))
                    db2.commit()

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            logger.error(f"Erro: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Erro interno.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")