from app.core.database import SessionLocal
from app.api.models import User

def deletar(external_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user:
            confirmation = input(f"Tem certeza que deseja excluir {user.full_name} ({user.role})? [S/N]: ")
            if confirmation.lower() == 's':
                db.delete(user)
                db.commit()
                print("Usuário excluído com sucesso.")
            else:
                print("Operação cancelada.")
        else:
            print("Usuário não encontrado.")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    target = input("Digite o ID (login) do usuário para EXCLUIR: ")
    deletar(target)