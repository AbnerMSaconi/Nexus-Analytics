# 🤖 UCDB IA - Sistema de RAG Acadêmico Híbrido (vLLM + GraphRAG)

O **UCDB-IA** é uma plataforma experimental modular de alto desempenho que utiliza **RAG Híbrido (Vetorial + Grafos)** para fornecer respostas precisas baseadas em documentos acadêmicos.

## 🚀 Novidades da Versão Otimizada
1.  **Estabilidade RAM (OOM Protection)**: Limites rígidos de memória via Docker e paralelismo reduzido para rodar liso em máquinas com 16GB de RAM.
2.  **Contexto Expandido (16k)**: Suporte a janelas de contexto de até 16.384 tokens para análise de documentos extensos.
3.  **MathJax & LaTeX**: Renderização profissional de fórmulas matemáticas e frações (ex: $\frac{3}{5}$) no chat.
4.  **PyMuPDF Engine**: Ingestão de PDFs até 10x mais rápida.
5.  **vLLM + PagedAttention**: KV Cache dinâmico para economia de VRAM.

---

## 📦 1. Pré-requisitos

1.  **Docker Desktop** com suporte a NVIDIA GPU.
2.  **NVIDIA Container Toolkit**.
3.  **Modelos GGUF/AWQ**:
    - LLM: `qwen2.5-3b-instruct-q4_k_m.gguf` (ou similar compatível com vLLM).
    - Embedding: `Qwen3-Embedding-0.6B-Q8_0.gguf`.
    - Localização: `%USERPROFILE%\.cache\llama.cpp`.

---

## 🛠️ 2. Execução Rápida

```powershell
./run.ps1
```

### 👤 Usuário Administrador
Crie a conta admin com o comando:
```powershell
docker exec -it ucdb-backend python create_admin.py
```

---

## 🏛️ 3. Arquitetura e Módulos
- **`app/core/rag.py`**: Cérebro do sistema com GraphRAG e busca vetorial.
- **`app/core/llm.py`**: Interface vLLM (OpenAI-compatible).
- **`quebrapdf.py`**: Fatiador inteligente ultra-rápido usando PyMuPDF.

---
© 2026 UCDB IA - Software Architecture & ML Engineering.
