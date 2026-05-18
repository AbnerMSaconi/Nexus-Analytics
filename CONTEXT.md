# CONTEXT.md — Nexus / DAC 4º Semestre

Mapeamento completo do que foi desenvolvido no projeto Nexus como Desafio de Articulação de Competências (DAC) do 4º semestre da UCDB.

---

## 1. Visão Geral do Projeto

**Nome:** Nexus — Plataforma de Análise de Dados Educacionais  
**Aluno:** Abner Matheus Moraes Saconi  
**Instituição:** Universidade Católica Dom Bosco (UCDB), Campo Grande, MS  
**Contexto:** DAC — Desafio de Articulação de Competências, componente de avaliação semestral da matriz curricular  
**Tema:** Monitoramento da ODS 4 (Educação de Qualidade) com dados da rede pública estadual do MS  
**Repositório:** https://github.com/AbnerMSaconi/Nexus-Analytics

---

## 2. Problema Resolvido

A SED-MS publica dados de matrículas por unidade escolar no portal de dados abertos do estado, um arquivo CSV por ano letivo. Para construir qualquer análise histórica é necessário baixar cada arquivo separadamente, padronizar cabeçalhos que mudam entre versões, lidar com encodings distintos e calcular totais manualmente. O Nexus elimina essa fricção.

**Base de dados consolidada:** 599 escolas, 79 municípios, 2018–2024 (7 anos).

---

## 3. O que Foi Construído

### 3.1 Backend (Python / FastAPI)

**Arquivo:** `backend/app/dac/`

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | Modelos SQLAlchemy: `DacEscola` e `DacDadosEscolares` |
| `classes.py` | Camada de domínio: `DadoAnual`, `Escola`, `Municipio`, `SerieHistorica` |
| `importer.py` | Pipeline de importação CSV com bulk insert e deduplicação automática |
| `routes.py` | 9 endpoints FastAPI do módulo DAC |
| `tools.py` | Funções auxiliares para o chat analítico |

**Banco de dados (SQLite):**
- `dac_escolas`: cadastro de unidades escolares com `UNIQUE(nome, municipio)`
- `dac_dados_escolares`: indicadores anuais com `UNIQUE(escola_id, ano)` — garante idempotência nas reimportações

**Pipeline de importação:**
1. Detecta encoding automaticamente (UTF-8, Latin-1, CP1252)
2. Normaliza cabeçalhos (variam entre versões dos CSVs)
3. Bulk insert com ignorar duplicatas por restrição de banco
4. Suporta múltiplos arquivos em uma operação
5. Retorna sumário: inseridos, ignorados, escolas novas

**Classes de domínio (in-memory):**
```
SerieHistorica
└── municipios: dict[str, Municipio]
    └── escolas: dict[str, Escola]
        └── historico: dict[int, DadoAnual]
```
- `DadoAnual`: contadores brutos + cálculo dinâmico de taxas (aprovação, reprovação, abandono)
- `SerieHistorica.resumo_para_llm()`: gera o texto estruturado injetado no prompt do LLM

**Estratégia de integração com LLM — Pré-busca Contextual:**  
Antes de cada resposta do chat, o backend executa a query SQL correspondente ao filtro ativo, formata os dados em texto estruturado com as taxas pré-calculadas e marcadas como `← RESPOSTA PRONTA`, e injeta esse contexto no prompt do sistema. O LLM não recalcula — apenas lê os valores. Isso eliminou erros aritméticos que ocorriam quando o contexto era passado como JSON.

**Modo de raciocínio (chain-of-thought):**  
O Qwen3 suporta tokens `/think` e `/no_think` para ativar/desativar o raciocínio encadeado. O bloco `<think>...</think>` é filtrado pelo backend antes de ser enviado ao cliente — o frontend recebe apenas a resposta final, com indicador visual durante o processamento.

**Detecção por regex no chat:**
- `_RE_EXCLUIR`: detecta pedidos de exclusão de anos ("desconsidere os dados de 2026")
- `_RE_ESTIM`: detecta pedidos de estimativa/projeção para aplicar tendência histórica
- Detecção de município e intervalo de anos para sobrepor filtros do dashboard

### 3.2 Frontend (React / TypeScript)

**Arquivo:** `frontend/src/components/DashboardDAC.tsx`

**Dashboard:**
- 4 KPIs: total de matrículas, taxa de aprovação, taxa de reprovação, taxa de abandono
- Gráfico de linha: evolução histórica de matrículas e taxas
- Gráfico de barras: comparativo por ano (aprovados, reprovados, abandono)
- Seletor de colunas: ativa/desativa métricas individualmente nos gráficos
- Filtros por município e intervalo de anos — atualizam sem recarregar a página
- Importação de CSV diretamente pelo dashboard (botão de upload)

**Chat analítico:**
- Painel flutuante expansível/minimizável sem interromper a sessão
- Streaming de resposta via SSE com renderização incremental
- Máquina de estados `aiPhase`: `idle → waiting → thinking → streaming → idle`
  - `waiting`: três pontos animados (aguardando primeira resposta)
  - `thinking`: ícone de chip pulsando + indicador violeta (modelo raciocínando)
  - `streaming`: texto sendo transmitido com cursor piscando
- Sessão preservada durante navegação (componente sempre montado, ocultado via CSS)
- Histórico de conversa mantido na memória do cliente

**Renderização de respostas:**
- `MarkdownMessage.tsx`: react-markdown + remark-math + rehype-katex
- Suporta markdown completo (negrito, listas, tabelas, código) e fórmulas LaTeX via KaTeX
- Substituiu MathJax CDN que causava conflitos com o CSP

**Acesso em rede local:**
- `utils/apiBase.ts`: URL do backend resolvida dinamicamente via `window.location.hostname`
- Todos os componentes (api.ts, apiService, storageService, Login, DocumentManager, SystemStatus) usam essa URL dinâmica
- Nenhuma URL hardcoded — funciona em localhost e em qualquer IP da rede local

### 3.3 Infraestrutura (Docker Compose)

Quatro serviços:

| Serviço | Imagem | Porta | Função |
|---|---|---|---|
| `llm` | ghcr.io/ggml-org/llama.cpp:server-cuda | 8080 | Serve Qwen3-8B via API OpenAI-compatible |
| `embeddings` | ghcr.io/ggml-org/llama.cpp:server-cuda | 8081 | Serve Qwen3-Embedding-0.6B |
| `backend` | build local (FastAPI) | 8000 | API REST + chat analítico |
| `frontend` | build local (Vite/React) | 5173 | Interface web |

**Configuração via `.env`:**
```env
LLM_MODEL=Qwen3-8B-Q4_K_M.gguf
EMBEDDING_MODEL=Qwen3-Embedding-0.6B-Q8_0.gguf
MODELS_DIR=D:/models
SECRET_KEY=...
LLM_CONTEXT=8192
LLM_PARALLEL=1
CUDA_DEVICE=0
```

**Hardware utilizado:** NVIDIA RTX 5060 (8 GB VRAM). O Qwen3-8B-Q4_K_M ocupa ~4,5 GB; com contexto 8192 tokens o total fica em ~6 GB.

**Monitoramento de GPU:** substituído `nvidia-smi` (binário não disponível no container Python) por `pynvml` — biblioteca Python que acessa a NVML diretamente.

### 3.4 Modelo LLM

**Modelo:** Qwen3-8B-Q4_K_M (quantização 4-bit)  
**Servidor:** llama.cpp com flag `--jinja` (necessária para o modo thinking)  
**Contexto:** 8192 tokens  
**Modo thinking:** tokens `/think` / `/no_think` — ativável pelo usuário via botão no chat  
**Gerenciamento de contexto com thinking ativo:** histórico reduzido para 4 mensagens / 300 chars para preservar espaço para o bloco `<think>`

---

## 4. Endpoints da API DAC

Base: `POST|GET /dac/`

| Método | Rota | Descrição |
|---|---|---|
| POST | `/dac/importar` | Importa um CSV (auth obrigatória) |
| POST | `/dac/importar-varios` | Importa múltiplos CSVs |
| GET | `/dac/status` | Estado do banco (escolas, anos disponíveis) |
| GET | `/dac/municipios` | Lista municípios com dados |
| GET | `/dac/anos` | Lista anos disponíveis |
| GET | `/dac/dashboard` | Dados agregados por município/ano |
| GET | `/dac/evolucao-estado` | Série histórica completa do estado |
| GET | `/dac/escolas` | Lista escolas com dados anuais |
| POST | `/dac/chat` | Chat analítico com streaming SSE |

---

## 5. Dados Analisados

Fonte: [Portal de Dados Abertos do MS — SED-MS](https://www.dados.ms.gov.br/dataset/matriculas-por-unidade-escolar)

| Ano | Matrículas | Aprovação | Reprovação | Abandono |
|-----|-----------|-----------|------------|---------|
| 2018 | 326.367 | 81,3% | 14,6% | 4,0% |
| 2019 | 293.195 | 86,7% | 13,2% | 0,1% |
| 2020 | 242.028 | 89,4% | 10,6% | n.d. |
| 2021 | 248.780 | 88,4% | 11,6% | n.d. |
| 2022 | 247.646 | 88,0% | 12,0% | n.d. |
| 2023 | 237.574 | 88,7% | 11,3% | n.d. |
| 2024 | 220.926 | 77,2% | 22,8% | n.d. |

Queda acumulada de matrículas: **−32,3%** (2018→2024).  
Anomalia 2024: taxa de reprovação mais que dobrou em relação a 2023 (11,3% → 22,8%).

---

## 6. Documentação Produzida

| Arquivo | Conteúdo |
|---|---|
| `docs/artigo_nexus.tex` | Artigo acadêmico completo (formato Elsevier/elsarticle, 5 páginas) |
| `docs/references.bib` | 10 referências bibliográficas (ONU, INEP, IEEE, arXiv) |
| `docs/DAC_TECNICO.md` | Documentação técnica: banco, ER diagram (Mermaid), API, classes |
| `docs/DAC_ACADEMICO.md` | Documentação acadêmica com motivação, arquitetura e análise dos dados |
| `docs/fig_admin.png` | Captura do painel administrativo (GPU, status dos serviços) |
| `docs/fig_dashboard_barras.png` | Captura do dashboard com gráfico de barras e chat analítico |
| `docs/fi_dashboard_linhas.png` | Captura do dashboard com gráfico de linha e chat analítico |
| `README.md` | Visão geral do projeto, configuração e estrutura do repositório |
| `CONTEXT.md` | Este arquivo — mapeamento completo do DAC |

---

## 7. Decisões Técnicas Relevantes

**Por que pré-busca contextual em vez de tool calling?**  
Nos testes iniciais com tool calling no formato OpenAI, o Qwen3 não disparava as funções de forma consistente. A pré-busca garante que o LLM sempre receba os dados, independente do comportamento do modelo.

**Por que contexto em texto e não JSON?**  
Quando o contexto chegava como JSON, o modelo tentava recalcular taxas a partir dos totais brutos e cometia erros aritméticos. Com texto estruturado e rótulos explícitos (`← RESPOSTA PRONTA`), o modelo passa a copiar os valores diretamente.

**Por que deduplicação no banco e não na aplicação?**  
`UNIQUE` constraints no banco garantem integridade mesmo em importações paralelas ou concorrentes, eliminando a janela de corrida que existiria com `SELECT` antes de cada `INSERT`.

**Por que janela de contexto 8192 tokens?**  
Com 4096 tokens, o bloco `<think>` do modo de raciocínio consumia toda a janela antes de produzir resposta. 8192 tokens resolve o problema sem estourar a VRAM disponível (~6 GB de 8 GB).

**Por que react-markdown + KaTeX em vez de MathJax?**  
MathJax via CDN conflitava com o CSP da aplicação e produzia renderização inconsistente. KaTeX processa markdown e LaTeX em uma única passagem, sem dependência externa.

---

## 8. Problemas Encontrados e Soluções

| Problema | Causa | Solução |
|---|---|---|
| LLM retornava 0% de reprovação | Regex não capturava "desconsidere os dados de 2026" | Ampliou `.{0,50}?` entre verbo e ano |
| Sem resposta no modo thinking | Contexto 4096 tokens esgotado pelo bloco `<think>` | Aumentou `LLM_CONTEXT` para 8192 |
| LLM recusava estimativas para 2025 | Regra "use apenas números do contexto" era absoluta | Adicionou exceção para estimativas explícitas |
| GPU mostrando "nvidia-smi não disponível" | Binário `nvidia-smi` ausente no container Python | Substituiu por `pynvml` |
| Chat perdido ao navegar para admin | `DashboardDAC` desmontado na mudança de rota | Componente sempre montado, ocultado via `display: none` |
| CSP bloqueando requisições | `SystemStatus` usava `127.0.0.1`, CSP só permitia `localhost` | Centralizou URL em `apiBase.ts` com `window.location.hostname` |
| Citações `[?]` no Overleaf | Sequência de compilação incompleta | Recompilar do zero (pdflatex → bibtex → pdflatex × 2) |
| `elsarticle-harvard.bst` não encontrado | Nome errado do arquivo de estilo | Corrigiu para `elsarticle-harv` |
