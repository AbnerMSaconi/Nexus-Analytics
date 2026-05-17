from app.core.database import SessionLocal, engine, Base
from app.api.models import User
from app.core.security import get_password_hash
import uuid

def create_initial_admin():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin_id = "admin"
        existing = db.query(User).filter(User.external_id == admin_id).first()
        hashed_pw = get_password_hash("admin123")
        if existing:
            existing.role = "administrador"
            existing.password_hash = hashed_pw
            existing.is_blocked = False
            db.commit()
            print(f"Usuário '{admin_id}' atualizado para administrador.")
        else:
            db.add(User(
                id=str(uuid.uuid4()),
                external_id=admin_id,
                full_name="Administrador",
                password_hash=hashed_pw,
                role="administrador",
                is_blocked=False,
            ))
            db.commit()
            print(f"Usuário '{admin_id}' criado (senha: admin123).")
    except Exception as e:
        print(f"Erro: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()
