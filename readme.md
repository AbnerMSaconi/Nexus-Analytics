# Nexus — Plataforma de Análise de Dados Educacionais

Plataforma web para consolidação e análise interativa de dados educacionais da rede pública estadual do Mato Grosso do Sul, desenvolvida como **Desafio de Articulação de Competências (DAC)** da Universidade Católica Dom Bosco (UCDB).

Alinhada à **ODS 4 — Educação de Qualidade** da Agenda 2030, a plataforma automatiza a importação dos CSVs anuais de matrículas publicados pela SED-MS, consolida os registros de 599 escolas em 79 municípios (2018–2024) e disponibiliza um dashboard interativo com assistente analítico baseado em LLM.

---

## Funcionalidades

- **Dashboard interativo** com KPIs (matrículas, aprovação, reprovação, abandono), gráficos de evolução histórica e comparativo por ano
- **Filtros dinâmicos** por município e intervalo de anos, sem recarregamento de página
- **Chat analítico** em linguagem natural com streaming de resposta via SSE
- **Modo de raciocínio** (chain-of-thought) com indicador visual durante o processamento
- **Importação de CSV** com deduplicação automática por restrição de banco — idempotente
- **Painel administrativo** com monitoramento de GPU, status dos serviços e gerenciamento de usuários
- **Acesso em rede local** — qualquer PC na rede pode acessar via IP do servidor

---

## Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                    │
│                                                     │
│  frontend  (Vite/React)       :5173                 │
│  backend   (FastAPI/SQLite)   :8000                 │
│  llm       (llama.cpp + CUDA) :8080                 │
│  embeddings (llama.cpp)       :8081                 │
└─────────────────────────────────────────────────────┘
```

| Camada       | Tecnologias                                      |
|--------------|--------------------------------------------------|
| Frontend     | React 18, TypeScript, TailwindCSS, Recharts      |
| Backend      | FastAPI, SQLAlchemy, SQLite, Pydantic            |
| LLM          | Qwen3-8B-Q4_K_M via llama.cpp (CUDA)            |
| Embeddings   | Qwen3-Embedding-0.6B-Q8_0 via llama.cpp         |
| Autenticação | JWT (Bearer token)                               |

---

## Pré-requisitos

- Docker e Docker Compose com suporte a GPU (NVIDIA Container Toolkit)
- GPU NVIDIA com pelo menos 6 GB de VRAM (testado em RTX 5060 8 GB)
- Arquivos `.gguf` dos modelos em um diretório local (ex: `D:/models`)

---

## Configuração

1. Copie o arquivo de exemplo e edite as variáveis:

```bash
cp .env.example .env
```

```env
LLM_MODEL=Qwen3-8B-Q4_K_M.gguf
EMBEDDING_MODEL=Qwen3-Embedding-0.6B-Q8_0.gguf
MODELS_DIR=D:/models          # caminho local para a pasta com os .gguf
SECRET_KEY=troque_por_chave_segura
LLM_CONTEXT=8192
LLM_PARALLEL=1
CUDA_DEVICE=0
```

2. Suba os serviços:

```bash
docker compose up -d
```

3. Crie o usuário administrador:

```bash
docker compose exec backend python utils/create_admin.py
```

4. Acesse em `http://localhost:5173` ou `http://<IP-do-servidor>:5173` na rede local.

---

## Dados

Os CSVs de matrículas por unidade escolar estão em `data/` e são publicados pela SED-MS no [Portal de Dados Abertos do MS](https://www.dados.ms.gov.br/dataset/matriculas-por-unidade-escolar). Podem ser importados pelo painel administrativo ou via `POST /dac/importar`.

Arquivos disponíveis: 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2026 (parcial).

---

## Documentação

| Documento               | Descrição                                             |
|-------------------------|-------------------------------------------------------|
| `docs/artigo_nexus.tex` | Artigo acadêmico (formato Elsevier/elsarticle)        |
| `docs/DAC_TECNICO.md`   | Documentação técnica: banco, API, classes de domínio  |
| `docs/DAC_ACADEMICO.md` | Documentação acadêmica do projeto                     |
| `docs/references.bib`   | Referências bibliográficas                            |

---

## Estrutura do Repositório

```
UCDB-IA/
├── backend/
│   ├── app/
│   │   ├── dac/          # Módulo DAC: models, classes, importer, routes
│   │   ├── api/          # Rotas gerais (auth, users, RAG)
│   │   └── core/         # Config, banco, LLM, embeddings, segurança
│   └── utils/            # Scripts de administração
├── frontend/
│   └── src/
│       ├── components/   # DashboardDAC, AdminPanel, Login, MarkdownMessage
│       ├── services/     # apiService, storageService
│       └── utils/        # apiBase.ts
├── data/                 # CSVs da SED-MS (2018–2024)
├── docs/                 # Artigo, documentação técnica, capturas de tela
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Autor

**Abner Matheus Moraes Saconi** — UCDB, Campo Grande, Brasil
abnermatheusmoraes@gmail.com
