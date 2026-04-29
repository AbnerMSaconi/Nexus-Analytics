# 🤖 UCDB IA - Sistema de RAG Acadêmico Inteligente (Versão Docker)

O **UCDB-IA** é uma plataforma de inteligência artificial que utiliza **RAG (Retrieval-Augmented Generation)** para fornecer respostas precisas baseadas em documentos acadêmicos. Esta versão foi totalmente otimizada para rodar em **Docker**, garantindo facilidade de instalação, isolamento de ambiente e aceleração por GPU NVIDIA.

---

## 📦 1. Pré-requisitos (Obrigatório)

Antes de começar, certifique-se de ter instalado:
1.  **Docker Desktop**: [Baixar aqui](https://www.docker.com/products/docker-desktop/)
2.  **NVIDIA Container Toolkit**: Necessário para aceleração por GPU.
3.  **Modelos de IA (GGUF)**:
    - Baixe o modelo LLM: [qwen2.5-3b-instruct-q4_k_m.gguf](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf)
    - Baixe o modelo de Embedding: [Qwen3-Embedding-0.6B-Q8_0.gguf](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf)
    - **Localização**: Coloque ambos os arquivos na pasta `%USERPROFILE%\.cache\llama.cpp`.

---

## 🚀 2. Como Rodar o Sistema

Abra um terminal PowerShell na raiz do projeto e execute:

```powershell
./run.ps1
```

O script cuidará automaticamente do build das imagens, instalação de dependências e inicialização dos containers.

### 👤 Criando o Usuário Administrador
Após a primeira inicialização, crie a conta admin com o comando:
```powershell
docker exec -it ucdb-backend python create_admin.py
```
*   **Acesso Padrão**: Usuário `admin` | Senha `admin123`

---

## 🌐 3. Endereços de Acesso

- **Interface Web (Frontend)**: [http://localhost:5173](http://localhost:5173)
- **API (Backend)**: [http://localhost:8000](http://localhost:8000)
- **Servidor de Chat (LLM)**: [http://localhost:8080](http://localhost:8080)
- **Servidor de Busca (Embedding)**: [http://localhost:8081](http://localhost:8081)

---

## 🛠️ 4. Comandos Úteis (Docker)

| Ação | Comando |
| :--- | :--- |
| **Iniciar o sistema** | `./run.ps1` |
| **Parar o sistema** | `docker-compose down` |
| **Ver logs em tempo real** | `docker-compose logs -f` |
| **Limpar containers e imagens** | `docker-compose down --rmi all` |
| **Acessar terminal do backend** | `docker exec -it ucdb-backend sh` |

---

## 📂 5. Estrutura do Projeto

- **`app/`**: API FastAPI e lógica central do RAG.
- **`frontend/`**: Interface moderna em React (Vite).
- **`pdfs/`**: Volume para armazenamento de documentos acadêmicos.
- **`embeddings/`**: Volume para índices de busca vetorial.
- **`docker-compose.yml`**: Orquestração dos 4 serviços do ecossistema.

---

## ⚠️ Solução de Problemas

- **Erro de GPU**: Se houver erros de "nvidia runtime", verifique se o NVIDIA Container Toolkit está corretamente configurado e se os drivers da GPU estão atualizados.
- **Modelos não encontrados**: Garanta que os arquivos `.gguf` estão exatamente no caminho `%USERPROFILE%\.cache\llama.cpp`.
- **Portas Ocupadas**: Certifique-se de que as portas 5173, 8000, 8080 e 8081 não estão sendo usadas por outros aplicativos.

---
© 2026 UCDB IA - Inteligência Artificial para Educação.
*Atualizado em 29 de Abril de 2026.*
