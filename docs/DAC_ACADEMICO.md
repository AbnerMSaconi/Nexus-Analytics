# Módulo DAC — Análise de Dados Educacionais do MS
## Documento Acadêmico — 4º Semestre

**Projeto**: UCDB-IA — Sistema de Inteligência Artificial Acadêmica  
**Módulo**: DAC (Dados Acadêmicos das Escolas) — ODS 4: Educação de Qualidade  
**Escopo**: Rede Pública de Ensino — Mato Grosso do Sul (2018–2026)

---

## 1. Introdução

A Agenda 2030 das Nações Unidas estabelece os Objetivos de Desenvolvimento Sustentável (ODS), sendo o **ODS 4 — Educação de Qualidade** voltado a garantir educação inclusiva, equitativa e de qualidade para todos. No Brasil, o acompanhamento desse objetivo depende da análise sistemática de indicadores como taxas de aprovação, reprovação e abandono escolar.

O presente módulo, denominado **DAC**, foi desenvolvido no contexto do sistema UCDB-IA com o objetivo de centralizar, visualizar e interpretar com auxílio de Inteligência Artificial os dados de matrículas da rede pública de Mato Grosso do Sul (MS), disponibilizados publicamente pelo governo estadual.

---

## 2. Problema e Motivação

A análise manual dos dados educacionais disponíveis (arquivos CSV com dezenas de milhares de registros por ano) é inviável sem ferramentas adequadas. Os desafios identificados foram:

- **Volume de dados**: dados de mais de 1.200 escolas em 79 municípios, de 2018 a 2026
- **Dispersão temporal**: arquivos separados por ano, sem visão histórica consolidada
- **Falta de análise interpretativa**: os dados brutos não revelam tendências ou causas por si só
- **Dificuldade de acesso**: poucos atores têm ferramentas para cruzar dados municipais e temporais

O módulo DAC resolve esses problemas ao integrar importação automatizada, visualização interativa e análise interpretativa por LLM.

---

## 3. Fonte dos Dados

Os dados utilizados provêm dos relatórios oficiais de matrículas por unidade escolar da **Secretaria de Educação do Estado de Mato Grosso do Sul**, disponíveis no portal de dados abertos estadual.

Cada arquivo CSV contém, por escola e ano:

- Total de matrículas e matrículas após o censo escolar
- Situação dos alunos: aprovados, reprovados, em abandono, transferidos, cancelados, cursando
- Identificação da unidade escolar e do município

Os arquivos cobrem o período de **2018 a 2026**, permitindo análise histórica de oito anos.

---

## 4. Arquitetura do Módulo

O módulo DAC segue a arquitetura do sistema UCDB-IA, composta por três camadas:

### 4.1 Camada de Dados (Backend)

Implementada em **Python (FastAPI + SQLAlchemy + SQLite**):

- **Modelo de banco**: duas tabelas — `dac_escolas` (cadastro de unidades escolares) e `dac_dados_escolares` (indicadores anuais por escola)
- **Pipeline de importação**: leitura e normalização de CSVs com bulk insert, detectando duplicatas automaticamente e calculando taxas no momento da ingestão
- **Classes de domínio**: hierarquia `DadoAnual → Escola → Municipio → SerieHistorica` para aggregation em memória e geração de contexto textual para o LLM

### 4.2 Camada de Apresentação (Frontend)

Implementada em **React + TypeScript + Recharts**:

- **Dashboard interativo** com filtros por município e por ano
- **KPIs em destaque**: total de matrículas, taxa de aprovação, taxa de abandono, taxa de reprovação
- **Gráficos históricos**: evolução de matrículas e taxas ao longo dos anos (estado ou município)
- **Gráfico comparativo**: aprovados, reprovados e abandono por ano (barras agrupadas)
- **Importação direta**: upload de arquivos CSV pelo próprio dashboard, sem necessidade de acesso ao servidor

### 4.3 Camada de Inteligência Artificial

Integração com o LLM do UCDB-IA via **chat analítico** com as seguintes características:

- O contexto é montado dinamicamente com dados reais do banco (serie histórica textual)
- O LLM recebe dados do estado, município ou ano específico conforme o filtro ativo
- As respostas são transmitidas em tempo real via **SSE (Server-Sent Events)**
- System prompt especializado em educação pública e ODS 4, com foco em análise baseada em evidências

---

## 5. Funcionalidades Implementadas

| Funcionalidade | Descrição |
|---|---|
| Importação de CSV | Upload de arquivos oficiais pelo dashboard, com bulk insert e deduplicação automática |
| Dashboard com filtros | Visualização por estado, município e/ou ano |
| KPIs dinâmicos | Indicadores atualizados conforme filtro selecionado |
| Gráfico de evolução | Linha temporal de matrículas (estado ou município específico) |
| Gráfico de taxas | Evolução de aprovação, abandono e reprovação ao longo dos anos |
| Gráfico comparativo | Barras agrupadas por ano com os três desfechos principais |
| Chat analítico IA | Perguntas em linguagem natural com respostas baseadas nos dados reais |
| API REST | 8 endpoints documentados para integração ou consumo externo |

---

## 6. Indicadores Monitorados

O módulo acompanha os seguintes indicadores educacionais, diretamente relacionados à ODS 4:

**Taxa de Aprovação** — proporção de alunos aprovados em relação ao total com resultado definido (aprovados + reprovados + abandono). Indica a eficácia do processo de ensino.

**Taxa de Abandono** — proporção de alunos que abandonaram a escola. É o indicador mais crítico para a ODS 4, pois representa a exclusão efetiva do sistema educacional.

**Taxa de Reprovação** — proporção de alunos reprovados. Taxas elevadas estão correlacionadas com maior risco de abandono futuro.

**Total de Matrículas** — indicador de acesso. Reduções consecutivas podem indicar deslocamento populacional, fechamento de escolas ou desmotivação.

---

## 7. Exemplo de Uso

### Cenário: Investigando o abandono escolar em um município

1. O usuário acessa `/dashboard` e seleciona o município **"Corumbá"**
2. O dashboard exibe os KPIs e gráficos históricos de Corumbá (2018–2026)
3. O usuário digita no chat analítico: *"A taxa de abandono de Corumbá aumentou nos últimos anos? Quais podem ser as causas?"*
4. O LLM recebe os dados reais de Corumbá como contexto e responde com análise baseada nos números, identificando tendências e possíveis fatores socioeconômicos

---

## 8. Considerações Técnicas

### Deduplicação de Dados
O importer verifica a existência do par `(escola_id, ano)` antes de inserir. Isso permite reimportar arquivos sem criar duplicatas, tornando o processo idempotente.

### Cálculo de Taxas
As taxas são calculadas no momento da importação sobre a base `(aprovados + reprovados + abandono)`, excluindo alunos ainda cursando ou com outras situações, para refletir apenas os resultados efetivos.

### Contexto para o LLM
O método `SerieHistorica.resumo_para_llm()` gera um resumo textual estruturado dos dados conforme o filtro ativo, garantindo que o LLM receba apenas informações pertinentes à pergunta do usuário — reduzindo alucinações e aumentando a precisão das análises.

---

## 9. Limitações e Trabalhos Futuros

| Limitação | Possível evolução |
|---|---|
| Dados apenas da rede pública estadual | Incluir rede municipal e federal |
| Escopo restrito ao MS | Expandir para outros estados |
| Análise por município, não por escola individualmente no frontend | Adicionar drill-down por escola |
| LLM sem memória entre perguntas do chat DAC | Implementar histórico de conversa no chat analítico |
| Sem exportação de relatórios | Adicionar geração de PDF/Excel com os dados filtrados |

---

## 10. Conclusão

O módulo DAC demonstra como dados educacionais públicos podem ser transformados em inteligência acionável por meio da combinação de engenharia de dados, visualização interativa e Inteligência Artificial. Ao alinhar o desenvolvimento ao ODS 4, o sistema contribui diretamente para o monitoramento e a conscientização sobre a qualidade da educação pública no Mato Grosso do Sul.

A integração com o LLM permite que usuários sem formação técnica em análise de dados possam interpretar tendências, identificar municípios em situação crítica e formular hipóteses sobre os fatores que influenciam os indicadores educacionais — democratizando o acesso à análise de dados públicos.
