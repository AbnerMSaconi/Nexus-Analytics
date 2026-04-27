# 🤖 UCDB IA - Sistema de RAG Acadêmico Inteligente

O **UCDB-IA** é uma plataforma de inteligência artificial de última geração que utiliza a técnica de **RAG (Retrieval-Augmented Generation)** para fornecer respostas precisas baseadas em documentos acadêmicos da UCDB. O sistema é otimizado para rodar com **aceleração por GPU (NVIDIA)**, garantindo respostas quase instantâneas.

---

## 🚀 Destaques de Performance (GPU)
- **Busca Vetorial Acelerada**: Utiliza `faiss-gpu` para pesquisar em milhares de páginas de documentos em milissegundos.
- **LLM Local Otimizado**: Configurado para carregar modelos GGUF diretamente na VRAM da placa de vídeo (GPU Offloading).
- **Processamento Paralelo**: A ingestão de novos documentos utiliza núcleos CUDA para extração de contexto.

---

## 📂 Documentação da Estrutura de Pastas

### 📂 `app/` (Cérebro do Backend)
Esta pasta contém toda a lógica do servidor FastAPI e as regras de negócio.
- **`api/`**: Contém as rotas (`routes.py`), modelos do banco de dados (`models.py`) e esquemas de validação (`schemas.py`).
- **`core/`**: Configurações centrais do sistema.
  - `config.py`: Configurações de GPU (`-ngl 99`) e caminhos do sistema.
  - `database.py`: Conexão com o banco de dados SQLite.
  - `security.py`: Lógica de Hash de senhas (Bcrypt) e Tokens JWT.
  - `rag.py`: Motor de busca semântica otimizado para GPU.
- **`utils/`**: Ferramentas auxiliares como logs e streaming de respostas.

### 📂 `frontend/` (Interface do Usuário)
Desenvolvido em **React + TypeScript + Vite**.
- **`src/components/`**: Interface do Chat, Painel Admin e Gerenciador de Documentos.
- **`src/services/`**: Comunicação com a API.
- **`src/assets/api.ts`**: URL centralizada (configurada para `127.0.0.1:8000`).

---

## 🧠 Como o RAG funciona neste sistema?
1. **Upload**: PDFs são enviados via Painel Administrativo.
2. **Fatiamento**: O `quebrapdf.py` divide os arquivos para melhor contexto.
3. **Vetorização**: O sistema usa o modelo de *Embedding* (via GPU se disponível).
4. **Busca Semântica**: O **FAISS** localiza os trechos mais relevantes para sua dúvida.
5. **Resposta**: A IA gera a resposta citando o nome do arquivo original.

---

## 🛡️ Segurança e Permissões
- **Administrador**: Gestão total de usuários e documentos.
- **Aluno**: Acesso restrito apenas aos conteúdos do seu curso.
- **Criptografia**: Todas as conversas são salvas com criptografia AES-256 no banco de dados.

---

## 🚀 Instalação Rápida
Consulte o arquivo **`INSTRUCOES_INSTALACAO.txt`** para configurar o ambiente de GPU ou CPU.

---
© 2026 UCDB IA - Inteligência Artificial para Educação.
