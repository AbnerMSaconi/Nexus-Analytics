from app.core.database import SessionLocal
from app.api.models import User
from app.core.security import get_password_hash
import uuid

def create_initial_admin():
    db = SessionLocal()
    try:
        # Usa o mesmo ID externo que você está tentando no Login
        admin_id = "admin"
        existing_admin = db.query(User).filter(User.external_id == admin_id).first()
        
        # Usa a função oficial do sistema para gerar o Hash
        hashed_pw = get_password_hash("admin123")
        
        if existing_admin:
            print(f"O usuário '{admin_id}' já existe. Atualizando cargo para administrador e resetando senha.")
            existing_admin.role = "administrador"
            existing_admin.password_hash = hashed_pw
            existing_admin.is_blocked = False
            db.commit()
            print("Usuário atualizado com sucesso.")
        else:
            new_admin = User(
                id=str(uuid.uuid4()),
                external_id=admin_id,
                full_name="Administrador do Sistema",
                password_hash=hashed_pw,
                role="administrador",
                course="Geral",
                is_blocked=False
            )
            db.add(new_admin)
            db.commit()
            print(f"Usuário '{admin_id}' criado com sucesso com a senha 'admin123'.")
            
    except Exception as e:
        print(f"Erro ao criar admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()
