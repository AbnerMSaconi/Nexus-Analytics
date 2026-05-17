from app.core.database import SessionLocal
from app.api.models import User

if __name__ == "__main__":
    external_id = input("ID (login) do usuário para promover a Admin: ")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id).first()
        if not user:
            print("Usuário não encontrado.")
        else:
            user.role = "administrador"
            db.commit()
            print(f"Sucesso: {external_id} agora é Administrador.")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        db.close()
