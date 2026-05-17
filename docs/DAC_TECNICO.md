# Módulo DAC — Documentação Técnica

Módulo de análise de dados educacionais da rede pública do Mato Grosso do Sul, integrado ao sistema UCDB-IA. Alinhado à ODS 4 (Educação de Qualidade) da ONU.

---

## Estrutura de Arquivos

```
app/dac/
├── __init__.py
├── models.py       # Modelos SQLAlchemy (tabelas do banco)
├── classes.py      # Classes de domínio (DadoAnual, Escola, Municipio, SerieHistorica)
├── importer.py     # Pipeline de importação CSV (bulk insert)
└── routes.py       # Router FastAPI com todos os endpoints

frontend/src/components/
└── DashboardDAC.tsx  # Dashboard React com gráficos e chat IA

Dados/
└── matriculas-por-unidade-escolar-YYYY.csv  # Arquivos de dados (2018–2026)
```

---

## Modelos de Banco de Dados

### `DacEscola`
Representa uma unidade escolar única (nome + município).

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | String (UUID) | Chave primária |
| `nome` | String | Nome da unidade escolar |
| `municipio` | String | Município (indexado) |

Constraint única: `(nome, municipio)`.

### `DacDadosEscolares`
Dados anuais de uma escola. Um registro por escola por ano.

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | String (UUID) | Chave primária |
| `escola_id` | FK → DacEscola | Escola referenciada |
| `ano` | Integer | Ano de referência (indexado) |
| `total_matriculas` | Integer | Total de matrículas |
| `matricula_inicial` | Integer | Matrículas no início do ano |
| `matricula_apos_censo` | Integer | Matrículas após o censo |
| `transferidos` | Integer | Alunos transferidos |
| `cancelados` | Integer | Matrículas canceladas |
| `falecido` | Integer | Óbitos registrados |
| `abandono` | Integer | Abandono escolar |
| `aprovados` | Integer | Alunos aprovados |
| `reprovados` | Integer | Alunos reprovados |
| `cursando` | Integer | Ainda cursando (sem resultado) |
| `outras_situacoes` | Integer | Outras situações |
| `taxa_aprovacao` | Float | % aprovação (calculado no import) |
| `taxa_abandono` | Float | % abandono |
| `taxa_reprovacao` | Float | % reprovação |

Constraint única: `(escola_id, ano)`.

---

## Classes de Domínio (`classes.py`)

Camada in-memory usada principalmente para gerar contexto textual ao LLM.

```
SerieHistorica
└── municipios: dict[str, Municipio]
    └── escolas: dict[str, Escola]
        └── historico: dict[int, DadoAnual]
```

- **`DadoAnual`**: dataclass com todos os campos de um ano. Calcula taxas dinamicamente.
- **`Escola`**: agrega histórico por ano.
- **`Municipio`**: agrega totais por ano (soma das escolas). Calcula taxas municipais.
- **`SerieHistorica`**: visão geral do estado. Gera o texto de contexto para o LLM via `resumo_para_llm()`.

---

## Pipeline de Importação CSV

`importer.py` → `importar_csv_bytes(conteudo, filename, db)`

1. Detecta o ano pelo nome do arquivo (`matriculas-...-2021.csv` → `2021`)
2. Lê o CSV com `csv.DictReader` (separador `;`, encoding `utf-8-sig`)
3. Calcula taxas de aprovação/abandono/reprovação
4. **Bulk insert de escolas**: cria apenas as escolas novas, evitando duplicatas
5. **Bulk insert de dados**: ignora registros `(escola_id, ano)` já existentes
6. Retorna sumário: registros inseridos, ignorados, escolas novas

Colunas esperadas no CSV:

| Coluna CSV | Campo Destino |
|---|---|
| `NomeMunicipio` | `DacEscola.municipio` |
| `NomeUnidadeEscolar` | `DacEscola.nome` |
| `AnoReferencia` | `DacDadosEscolares.ano` |
| `MatriculasTotal` | `total_matriculas` |
| `MatriculaInicial` | `matricula_inicial` |
| `MatriculaAposCenso` | `matricula_apos_censo` |
| `Transferidos` | `transferidos` |
| `Cancelados` | `cancelados` |
| `Falecido` | `falecido` |
| `Abandono` | `abandono` |
| `Aprovados` | `aprovados` |
| `Reprovados` | `reprovados` |
| `Cursando` | `cursando` |
| `OutrasSituacoes` | `outras_situacoes` |

---

## Endpoints da API

Base URL: `/dac`  
Tag OpenAPI: `DAC - Educação MS`

### `POST /dac/importar`
Importa um arquivo CSV para o banco.

- **Auth**: Bearer token obrigatório
- **Body**: `multipart/form-data` com campo `file` (`.csv`)
- **Response**:
```json
{
  "status": "ok",
  "arquivo": "matriculas-por-unidade-escolar-2021.csv",
  "ano": 2021,
  "registros_inseridos": 4823,
  "registros_ignorados": 0,
  "escolas_novas": 1247
}
```

### `GET /dac/status`
Estado geral do banco DAC.

```json
{
  "total_escolas": 1247,
  "total_registros": 9846,
  "anos_disponiveis": [2018, 2019, 2020, 2021, 2022, 2023, 2024],
  "importado": true
}
```

### `GET /dac/municipios`
Lista todos os municípios com dados no banco.

```json
["Campo Grande", "Corumbá", "Dourados", ...]
```

### `GET /dac/anos`
Lista os anos disponíveis no banco.

```json
[2018, 2019, 2020, 2021, 2022, 2023, 2024]
```

### `GET /dac/dashboard`
Dados agregados por município e ano para os gráficos.

**Query params**: `municipio` (opcional), `ano` (opcional)

```json
[
  {
    "municipio": "Campo Grande",
    "ano": 2021,
    "total_escolas": 312,
    "total_matriculas": 87450,
    "aprovados": 71200,
    "reprovados": 8900,
    "abandono": 3200,
    "transferidos": 4150,
    "taxa_aprovacao": 85.7,
    "taxa_abandono": 3.85,
    "taxa_reprovacao": 10.71
  }
]
```

### `GET /dac/evolucao-estado`
Evolução histórica agregada de todo o estado MS (sem filtros).

Mesmo formato do `/dashboard`.

### `GET /dac/escolas`
Lista escolas com seus dados anuais.

**Query params**: `municipio` (opcional), `ano` (opcional), `limit` (padrão 50, máx 200)

Ordenado por `total_matriculas` decrescente.

### `POST /dac/chat`
Chat analítico com IA usando dados reais como contexto. Resposta em SSE streaming.

- **Auth**: Bearer token obrigatório
- **Body**:
```json
{
  "message": "Quais municípios têm maior taxa de abandono?",
  "municipio": "Campo Grande",
  "ano": 2022
}
```
- **Response**: `text/event-stream`
```
data: {"type": "chunk", "content": "Com base nos dados..."}
data: {"type": "complete"}
```

---

## Frontend — DashboardDAC.tsx

Rota: `/dashboard`

### Componentes visuais

| Seção | Descrição |
|---|---|
| Header | Status do banco (escolas/registros), botão de importação CSV |
| Filtros | Seletor de município e ano |
| KPIs | Cards: Matrículas, Taxa Aprovação, Taxa Abandono, Taxa Reprovação |
| Gráfico 1 | LineChart — Evolução de matrículas (estado ou município) |
| Gráfico 2 | LineChart — Taxas históricas (%) |
| Gráfico 3 | BarChart — Aprovados / Reprovados / Abandono por ano |
| Chat IA | Sidebar com chat analítico em streaming |

### Cores usadas

| Indicador | Cor |
|---|---|
| Matrículas | `#3b82f6` (azul) |
| Aprovação | `#22c55e` (verde) |
| Abandono | `#ef4444` (vermelho) |
| Reprovação | `#f59e0b` (amarelo) |

---

## Como Carregar os Dados

1. Acesse o sistema autenticado
2. Navegue para `/dashboard`
3. Clique em **Carregar CSV**
4. Selecione um arquivo `matriculas-por-unidade-escolar-YYYY.csv`
5. Repita para cada ano disponível em `Dados/`

Os arquivos são processados em bulk: escolas duplicadas e registros já existentes são ignorados automaticamente.

---

## Integração com o Sistema Principal

O módulo se integra ao UCDB-IA via:

- `main.py` (raiz): importa `dac_router` e `dac_models`, registra tabelas e rotas
- `app/core/llm.py`: o endpoint `/dac/chat` usa o mesmo LLM do chat principal
- `app/core/security.py`: autenticação JWT compartilhada nos endpoints protegidos
