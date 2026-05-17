from app.core.database import SessionLocal
from app.api.models import User

if __name__ == "__main__":
    external_id = input("ID (login) do usuário para EXCLUIR: ")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id).first()
        if not user:
            print("Usuário não encontrado.")
        else:
            confirm = input(f"Excluir {user.full_name} ({user.role})? [S/N]: ")
            if confirm.lower() == "s":
                db.delete(user)
                db.commit()
                print("Usuário excluído.")
            else:
                print("Cancelado.")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        db.close()
