# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.api import models
from cryptography.fernet import Fernet
import os
import bcrypt

# Configuração JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# --- SISTEMA DE CRIPTOGRAFIA DE MENSAGENS ---
_key_str = os.getenv("MSG_ENCRYPTION_KEY", "w0zH_rB3k8Y7a2P1m9X_v5N4c6Q_l8J2t5E_o9T3m6Y=")
cipher_suite = Fernet(_key_str.encode())

def encrypt_message(content: str) -> str:
    if not content: return ""
    return cipher_suite.encrypt(content.encode()).decode()

def decrypt_message(token: str) -> str:
    try:
        if not token: return ""
        return cipher_suite.decrypt(token.encode()).decode()
    except Exception:
        return "[Conteúdo Indisponível/Erro de Decriptografia]"

# --- NOVO SISTEMA DE HASH COM BCRYPT DIRETO (CORRIGE ERRO 500) ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    # Gera o salt e o hash usando bcrypt nativo
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# --- JWT E AUTH ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except Exception:
        raise HTTPException(status_code=401, detail="Token expirado ou inválido")
        
    user = db.query(models.User).filter(models.User.external_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Conta bloqueada.")
        
    return user
