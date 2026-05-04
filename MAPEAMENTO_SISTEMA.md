# 🗺️ Mapeamento do Sistema UCDB-IA

Este documento descreve toda a arquitetura, funcionalidades e abrangência técnica do sistema **UCDB-IA** desenvolvido até o momento.

---

## 🏗️ 1. Arquitetura Geral
O sistema é uma aplicação de **RAG (Retrieval-Augmented Generation)** de nível empresarial, projetada para servir a comunidade acadêmica com foco em segurança, precisão técnica e experiência do usuário.

| Camada | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Frontend** | React + TypeScript + Tailwind | Interface moderna, responsiva e com suporte a MathJax/LaTeX. |
| **Backend** | FastAPI (Python) | API de alta performance com suporte a streaming de dados e segurança reforçada. |
| **Inteligência Artificial** | llama.cpp (vLLM-compat) + FAISS | Motor de busca híbrido otimizado para hardware com 16GB RAM. |
| **Banco de Dados** | SQLite + SQLAlchemy | Persistência de usuários, conversas e logs de auditoria. |
| **Processamento de Docs** | PyMuPDF (fitz) + Sliding Window | Extração ultra-rápida e divisão inteligente baseada em contextos. |

---

## 🛡️ 2. Segurança e Governança
Funcionalidades reforçadas para garantir a integridade total.

| Funcionalidade | Descrição | Status |
| :--- | :--- | :--- |
| **RBAC Blindado** | Bloqueio de forja de cargos no `/signup`. Admins apenas via terminal. | ✅ Reforçado |
| **OOM Protection** | Limites rígidos de RAM por container (Docker) para evitar travamento do host. | ✅ Ativo |
| **Path Traversal** | Sanitização rigorosa de nomes de arquivos usando `os.path.basename`. | ✅ Ativo |
| **Criptografia** | Mensagens de chat são criptografadas no banco (AES-256). | ✅ Ativo |

---

## 🧠 3. Motor de IA e Otimizações
O sistema utiliza uma arquitetura híbrida otimizada para estabilidade e contexto.

| Recurso | Descrição | Área de Impacto |
| :--- | :--- | :--- |
| **16k Context Window** | Capacidade de processar até 16.384 tokens por requisição. | Inferência |
| **Low Parallelism** | Processamento serializado (`--parallel 1`) para evitar picos de memória. | Estabilidade |
| **MathJax/LaTeX** | Renderização de fórmulas matemáticas complexas e frações elegantes. | UI/UX |
| **PyMuPDF Engine** | Substituição do pypdf pelo fitz, aumentando a velocidade em até 10x. | Ingestão |

---

## 📄 4. Gestão de Documentos
O sistema possui um pipeline de processamento de documentos avançado.

| Função | O que faz | Arquivo Base |
| :--- | :--- | :--- |
| **Smart PDF Splitter** | Detecta sumários e quebra PDFs gigantes em capítulos menores automaticamente. | `quebrapdf.py` |
| **Vetorização Automática** | Transforma texto em vetores numéricos para busca rápida. | `app/core/rag.py` |
| **Manifesto de Áreas** | Arquivo `manifest.json` que mapeia títulos, páginas e status de cada documento. | `app/core/rag.py` |

---

## 💻 5. Interface do Usuário (UX/UI)
Funcionalidades focadas na produtividade e clareza.

| Componente | Funcionalidades Principais |
| :--- | :--- |
| **Chat Interface** | LaTeX, Auto-grow textarea, Histórico, Sumário de Fontes Automático. |
| **Painel de Admin** | Gestão de usuários, alteração de cargos, desbloqueio de contas. |
| **Gerenciador de Docs** | Visualização em árvore das áreas de conhecimento e status de indexação. |

---

## 📈 6. Abrangência por Área de Conhecimento
Como o sistema se comporta em cada curso (Personas):

1. **Direito/Geral**: Foco em objetividade técnica, sem rodeios e fiel ao contexto oficial.
2. **Exatas**: Renderização de fórmulas e cálculos via MathJax para clareza acadêmica.
3. **Padrão**: Respostas sem citações no corpo do texto (fontes ficam no sumário inferior).

---
*Mapeamento atualizado em 04 de Maio de 2026 após otimização de RAM e Contexto.*
