# UCDB-IA 🧠💬

Bem-vindo ao **UCDB-IA**, um assistente acadêmico inteligente projetado para responder perguntas complexas com base em documentos internos. Este projeto utiliza uma arquitetura **RAG (Retrieval-Augmented Generation)** para combinar o poder de um Modelo de Linguagem (LLM) local com a privacidade e especificidade dos seus arquivos PDF.

## ✨ Funcionalidades

- **Arquitetura RAG Local**: Respostas geradas estritamente com base nos seus documentos, minimizando alucinações e garantindo privacidade.
- **LLM & Embeddings Locais**: Executa modelos de IA localmente via `llama.cpp` (suporte a GPU/CPU), sem enviar dados para nuvens de terceiros.
- **Interface Moderna (React)**: Novo frontend desenvolvido em React, Vite e TailwindCSS, com suporte a chat em tempo real (*streaming*), formatação Markdown e fórmulas matemáticas (MathJax).
- **Gestão de Documentos**: Sistema automático de ingestão de PDFs. Basta colocar os arquivos na pasta, e o sistema gera títulos e indexa o conteúdo automaticamente.
- **Citações Precisas**: As respostas indicam os documentos e trechos utilizados como fonte.
- **Histórico e Autenticação**: Sistema de login, registro de usuários e persistência de histórico de conversas.

## ⚙️ Tecnologias

### Backend
- **Python 3.10+** & **FastAPI**: API performática e assíncrona.
- **LangChain**: Orquestração do fluxo RAG e processamento de texto.
- **FAISS**: Banco de dados vetorial local de alta performance.
- **SQLAlchemy (SQLite)**: Gerenciamento de usuários e sessões.

### Frontend
- **React 19** & **Vite**: Interface rápida e responsiva.
- **TailwindCSS**: Estilização moderna.
- **Lucide React**: Ícones visuais.

### IA Core
- **Llama.cpp**: Servidor de inferência para LLMs (ex: Llama-3, Hermes) e modelos de Embedding (ex: Qwen, Nomic).

## 📂 Estrutura do Projeto

```
ucdb-ia/
├── app/                    # Lógica do Backend (FastAPI)
│   ├── api/                # Rotas e Schemas
│   ├── core/               # Config (config.py), Segurança, RAG, LLM
│   └── utils/              # Loggers
├── frontend/               # Aplicação React (Interface Principal)
│   ├── src/
│   │   ├── components/     # Chat, Login, DocumentManager
│   │   └── services/       # Integração com API
├── pdfs/                   # Coloque seus documentos PDF aqui
├── embeddings/             # (Gerado) Índices vetoriais FAISS
├── ucdb_ia.db              # (Gerado) Banco de dados SQLite
├── main.py                 # Ponto de entrada do Backend
└── requirements.txt        # Dependências Python
```

## 🚀 Instalação e Configuração

### Pré-requisitos
1. **Python 3.10+**
2. **Node.js & npm** (para o frontend)
3. **Llama.cpp (Server)**: Tenha o executável `llama-server` instalado ou compilado.

### Passo 1: Configurar o Backend

1. Clone o repositório e entre na pasta:
  ```bash
  git clone https://github.com/seu-usuario/ucdb-ia.git
  cd ucdb-ia
  ```

2. Crie e ative um ambiente virtual:
  ```bash
  python -m venv venv
  # Windows: venv\Scripts\activate
  # Linux/Mac: source venv/bin/activate
  ```

3. Instale as dependências:
  ```bash
  pip install -r requirements.txt
  ```

4. Prepare a pasta de documentos:
  ```bash
  mkdir pdfs
  ```

### Passo 2: Configurar o Frontend

1. Acesse a pasta do frontend:
  ```bash
  cd frontend
  ```

2. Instale as dependências:
  ```bash
  npm install
  ```

### Passo 3: Baixar Modelos de IA
Baixe dois modelos `.gguf` do HuggingFace:
1. **Modelo de Chat (LLM)**: Ex: `Hermes-3-Llama-3.1-8B.Q4_K_M.gguf`
2. **Modelo de Embedding**: Ex: `Qwen-Embedding-0.6B.gguf`

*Edite `app/core/config.py` se os nomes ou caminhos dos seus modelos forem diferentes.*

---

## 🏃‍♂️ Executando o Sistema

O sistema opera com 3 serviços simultâneos. Abra **3 terminais** diferentes:

### Terminal 1: Servidor de Embeddings
```bash
llama-server -m caminho/para/Qwen-Embedding.gguf --port 8081 --embedding -ngl 99
```

### Terminal 2: Servidor LLM
```bash
llama-server -m caminho/para/Llama-3.gguf --port 8080 -c 8192 -ngl 99 -fa 1
```

### Terminal 3: Aplicação Principal
```bash
python main.py
```

Para o frontend em desenvolvimento, abra um 4º terminal:
```bash
cd frontend && npm run dev
```

## 🖥️ Como Usar

- **Acesso**: http://localhost:5173 (Dev) ou http://localhost:8000 (Prod)
- **Login**: admin / admin (mock dev) ou registre um novo usuário
- **Base de Conhecimento**: PDFs na pasta `pdfs/` são processados automaticamente
- **Chat**: Selecione uma área e faça sua pergunta

## 🔧 Configuração Avançada

Edite `app/core/config.py`:
- `CHUNK_SIZE`: Tamanho dos pedaços de texto (padrão: 250)
- `RETRIEVAL_K`: Quantidade de trechos buscados (padrão: 5)
- `TEMPERATURE`: Criatividade do modelo (0.0 a 1.0)
