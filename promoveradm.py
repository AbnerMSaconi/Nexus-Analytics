from app.core.database import SessionLocal
from app.api.models import User

def promover_usuario(external_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.external_id == external_id).first()
        if user:
            user.role = "administrador"
            db.commit()
            print(f"Sucesso: Usuário {external_id} agora é Administrador.")
        else:
            print("Usuário não encontrado.")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Coloque o login/email do usuário que você quer promover
    usuario_para_promover = input("Digite o ID (login) do usuário para virar Admin: ")
    promover_usuario(usuario_para_promover)