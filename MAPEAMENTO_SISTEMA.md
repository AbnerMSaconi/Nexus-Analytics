# 🗺️ Mapeamento do Sistema UCDB-IA

Este documento descreve toda a arquitetura, funcionalidades e abrangência técnica do sistema **UCDB-IA** desenvolvido até o momento.

---

## 🏗️ 1. Arquitetura Geral
O sistema é uma aplicação de **RAG (Retrieval-Augmented Generation)** de nível empresarial, projetada para servir a comunidade acadêmica com foco em segurança, precisão técnica e experiência do usuário.

| Camada | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Frontend** | React + TypeScript + Tailwind | Interface moderna, responsiva e com foco em acessibilidade. |
| **Backend** | FastAPI (Python) | API de alta performance com suporte a streaming de dados. |
| **Inteligência Artificial** | LangChain + FAISS + vLLM | Motor de busca vetorial e integração com modelos de linguagem locais. |
| **Banco de Dados** | SQLite + SQLAlchemy | Persistência de usuários, conversas e logs de auditoria. |
| **Processamento de Docs** | PyMuPDF + Fatiador Inteligente | Extração e divisão de PDFs complexos baseada em sumários. |

---

## 🛡️ 2. Segurança e Governança
Funcionalidades implementadas para garantir a integridade dos dados e o controle de acesso.

| Funcionalidade | Descrição | Status |
| :--- | :--- | :--- |
| **RBAC (Role-Based Access Control)** | Controle de acesso granular para Alunos, Professores, Coordenadores e Admins. | ✅ Ativo |
| **Criptografia de Mensagens** | Mensagens de chat são criptografadas no banco (AES-256) e descriptografadas apenas para o usuário dono. | ✅ Ativo |
| **Auditoria de Acesso** | Registro de todos os eventos (Login, Ingestão, Erros, Bloqueios) na tabela `access_logs`. | ✅ Ativo |
| **Gatilho de Bloqueio** | Bloqueio automático de usuários após 5 tentativas falhas ou atividades suspeitas. | ✅ Ativo |
| **Isolamento de Cursos** | Alunos só acessam bases de conhecimento do seu curso ou a base "Geral". | ✅ Ativo |

---

## 🧠 3. Motor de IA e RAG (Cérebro do Sistema)
A inteligência do sistema não apenas responde, mas assume identidades baseadas no contexto.

| Recurso | Descrição | Área de Impacto |
| :--- | :--- | :--- |
| **Personas Dinâmicas** | IA muda o tom e regras conforme a área (Direito, Engenharia, Saúde, Tecnologia). | Chat |
| **Citações e Fontes** | Exibe exatamente de qual documento e página a resposta foi extraída. | Respostas |
| **Gerador de Tópicos** | IA analisa o PDF e cria automaticamente um título descritivo para o manifesto. | Ingestão |
| **Busca Semântica** | Uso de FAISS para encontrar trechos relevantes mesmo sem palavras-chave exatas. | Recuperação |
| **Selective Ingest** | Possibilidade de atualizar apenas uma área específica sem reprocessar tudo. | Administração |

---

## 📄 4. Gestão de Documentos
O sistema possui um pipeline de processamento de documentos avançado.

| Função | O que faz | Arquivo Base |
| :--- | :--- | :--- |
| **Smart PDF Splitter** | Detecta sumários e quebra PDFs gigantes em capítulos menores automaticamente. | `quebrapdf.py` |
| **Vetorização Automática** | Transforma texto em vetores numéricos para busca rápida. | `app/core/rag.py` |
| **Manifesto de Áreas** | Arquivo `manifest.json` que mapeia títulos, páginas e status de cada documento. | `app/core/rag.py` |
| **Upload via Frontend** | Interface para arrastar e soltar arquivos diretamente para uma área de curso. | `DocumentManager.tsx` |

---

## 💻 5. Interface do Usuário (UX/UI)
Funcionalidades focadas na produtividade e clareza.

| Componente | Funcionalidades Principais |
| :--- | :--- |
| **Chat Interface** | Markdown, Renderização de Fórmulas Matemáticas (MathJax), Auto-grow textarea, Histórico. |
| **Painel de Admin** | Gestão de usuários, alteração de cargos, desbloqueio de contas e deleção permanente. |
| **Gerenciador de Docs** | Visualização em árvore das áreas de conhecimento e status de indexação. |
| **Login/Auth** | Sistema de Token JWT, persistência de sessão e feedback de erros de segurança. |

---

## 🛠️ 6. Scripts e Utilitários de Raiz
Ferramentas de linha de comando para manutenção rápida.

| Script | Finalidade |
| :--- | :--- |
| `main.py` | Ponto de entrada do backend e orquestrador de serviços. |
| `quebrapdf.py` | Ferramenta independente para processar PDFs em lote. |
| `promoveradm.py` | Utilitário para elevar um usuário ao cargo de administrador via terminal. |
| `excluiruser.py` | Remoção limpa de usuários e todos os seus dados vinculados. |
| `requirements.txt` | Lista de todas as dependências Python do ecossistema. |

---

## 📈 7. Abrangência por Área de Conhecimento
Como o sistema se comporta em cada curso (Personas):

1. **Direito**: Foco em literalidade, leis e artigos. Recusa opiniões fora da base legal.
2. **Engenharia**: Foco em normas (ABNT), cálculos e pragmatismo. Respostas estruturadas em passos.
3. **Tecnologia**: Foco em documentação de código, arquitetura de sistemas e solução de bugs.
4. **Saúde**: Tom científico, proibição de prescrição diagnóstica, foco em protocolos clínicos.
5. **Geral**: Assistente educado e direto para áreas não categorizadas.

---
*Mapeamento gerado em 27 de Abril de 2026.*
