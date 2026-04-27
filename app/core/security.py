# app/core/security.py
from datetime import datetime, timedelta
from typing import Optional, Any, Union
from jose import jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.api import models
from cryptography.fernet import Fernet
import os

# Configuração de contexto para Hashing de Senhas (Segurança de Acesso)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

# Configurações JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ### INICIO DO SISTEMA DE CRIPTOGRAFIA DE MENSAGENS ###
# Usamos uma chave fixa como fallback para evitar perda de dados no desenvolvimento.
# Em produção, defina a variável de ambiente MSG_ENCRYPTION_KEY.
_default_key = b"V-7x2L3Q_xN_1b9M0z5F-R_uA4w8K2p5E_o9T3m6Y= " # Chave Fernet válida de 32 bytes codificada em base64 (ajustada para 44 chars)
_default_key_valid = Fernet.generate_key() # Gera uma chave válida como fallback se o dev não setar, mas usaremos uma estática
_key_str = os.getenv("MSG_ENCRYPTION_KEY", "w0zH_rB3k8Y7a2P1m9X_v5N4c6Q_l8J2t5E_o9T3m6Y=")
cipher_suite = Fernet(_key_str.encode())

def encrypt_message(content: str) -> str:
    """Criptografa o texto da mensagem antes de salvar no banco."""
    if not content: return ""
    return cipher_suite.encrypt(content.encode()).decode()

def decrypt_message(token: str) -> str:
    """Descriptografa o texto ao recuperar do banco para mostrar ao usuario."""
    try:
        if not token: return ""
        return cipher_suite.decrypt(token.encode()).decode()
    except Exception:
        return "[Conteúdo Indisponível/Erro de Decriptografia]"
# ### FIM DO SISTEMA DE CRIPTOGRAFIA DE MENSAGENS ###

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ### ATUALIZACAO: RECUPERACAO DE USUARIO COM VERIFICACAO DE BLOQUEIO ###
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
    except Exception:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
        
    user = db.query(models.User).filter(models.User.external_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    
    # Verifica se o usuario esta bloqueado pelo sistema de seguranca
    if user.is_blocked:
        raise HTTPException(
            status_code=403, 
            detail="Sua conta foi temporariamente bloqueada por atividades suspeitas. Contate o administrador."
        )
        
    return user