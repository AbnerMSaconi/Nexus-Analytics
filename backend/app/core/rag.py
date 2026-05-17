import os
import json
import re
import asyncio
from pathlib import Path
from datetime import datetime
from operator import itemgetter
from app.utils.websocket_manager import manager
from typing import List, Dict, Any

# --- IMPORTS LANGCHAIN ---
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage

try:
    from langchain_community.vectorstores import FAISS
except ImportError:
    print("\n" + "!"*60)
    print("ERRO CRÍTICO: O pacote 'faiss' não foi encontrado.")
    print("Por favor, execute: pip install faiss-cpu")
    print("!"*60 + "\n")
    raise

from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- IMPORTS DO PROJETO ---
from app.utils.logger import logger
from app.core.config import settings
from app.core.embeddings import get_embeddings
from app.core.llm import get_llm
from functools import lru_cache
import collections
from concurrent.futures import ThreadPoolExecutor
from app.utils.performance import monitor_perf, PerformanceMonitor

# Executor global para tarefas síncronas pesadas (I/O de arquivos FAISS)
_io_executor = ThreadPoolExecutor(max_workers=4)

# Cache com limite de tamanho para evitar estouro de memória (LRU básico)
class VectorStoreCache:
    def __init__(self, maxsize=5):
        self.cache = collections.OrderedDict()
        self.maxsize = maxsize

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)
            
    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

_vs_cache = VectorStoreCache(maxsize=3) # Mantém apenas 3 áreas em RAM simultaneamente

@lru_cache(maxsize=1)
def get_cached_embeddings():
    return get_embeddings()

@lru_cache(maxsize=1)
def get_cached_llm():
    return get_llm()

# ==============================================================================
# 1. UTILITÁRIOS
# ==============================================================================

import unicodedata

def _normalizar_nome_area(nome_pasta: str) -> str:
    # Remove acentos e caracteres especiais
    nfkd_form = unicodedata.normalize('NFKD', nome_pasta)
    apenas_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    # Converte para minúsculo, remove espaços e caracteres não alfanuméricos
    limpo = apenas_ascii.lower().strip().replace(" ", "_")
    return re.sub(r'[^a-z0-9_]', '', limpo)

def _is_pdf_image_only(file_path: str) -> bool:
    """Verifica se o PDF é apenas imagem usando pypdf (mais leve que pdfplumber)."""
    try:
        reader = PdfReader(file_path)
        text_content = ""
        # Verifica as 3 primeiras páginas
        for i in range(min(3, len(reader.pages))):
            text_content += reader.pages[i].extract_text() or ""
        
        return len(text_content.strip()) < 50
    except:
        return False

def _get_loader(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return PyPDFLoader(file_path)
    elif ext == '.docx':
        return Docx2txtLoader(file_path)
    elif ext == '.txt':
        return TextLoader(file_path, encoding='utf-8')
    return None

def carregar_manifesto(caminho_indice: str) -> dict:
    p = os.path.join(caminho_indice, "manifest.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def salvar_manifesto(caminho_indice: str, dados: dict):
    with open(os.path.join(caminho_indice, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def format_docs(docs):
    return "\n\n".join(f"[Fonte: {os.path.basename(d.metadata.get('source', 'Doc'))}] {d.page_content}" for d in docs)

@monitor_perf("Reranking de Documentos")
def _rerank_documents(question: str, docs: List[Any]) -> List[Any]:
    """
    Otimização de Reranking: Filtra e ordena documentos para garantir alta relevância.
    """
    if not docs: return []

    # 1. Filtro básico de qualidade (menos agressivo: 20 chars)
    docs = [d for d in docs if len(d.page_content.strip()) > 20]

    if not question: return docs[:settings.RETRIEVAL_K]

    # 2. Reranking por frequência de termos (Melhorado)
    # Filtramos palavras irrelevantes (stop words simples)
    stop_words = {"a", "o", "de", "do", "da", "em", "um", "uma", "com", "no", "na", "para"}
    words = set(re.findall(r'\w+', question.lower())) - stop_words

    scored_docs = []
    for d in docs:
        content_lower = d.page_content.lower()
        score = 0
        
        # Match de palavras individuais
        for w in words:
            if w in content_lower:
                score += 5 # Aumentamos o peso do match de palavra
                
        # Bônus para bigramas (proximidade de termos)
        # Se duas palavras da pergunta aparecem próximas, o score sobe muito
        for w1 in words:
            for w2 in words:
                if w1 != w2 and f"{w1} {w2}" in content_lower:
                    score += 10

        # Bônus se as palavras aparecerem no tópico/título
        topic = d.metadata.get("topic", "").lower()
        for w in words:
            if w in topic:
                score += 3
                
        scored_docs.append((score, d))

    # Ordena pelo score e pega os top K
    scored_docs.sort(key=lambda x: x[0], reverse=True)

    # Retorna os documentos que possuem ao menos algum match de palavra-chave
    final_docs = [d for score, d in scored_docs if score > 0]
    
    # Se não houver nenhum match de palavra-chave, retornamos o top 4 do FAISS 
    # (Aumentamos de 2 para 4 para dar mais chance ao modelo)
    if not final_docs: 
        logger.warning(f"Nenhum match de palavra-chave para a pergunta. Enviando top 4 do FAISS.")
        return docs[:4] 

    return final_docs[:settings.RETRIEVAL_K]

def _sanitizar_resposta(texto: str) -> str:
    if not texto: return ""
    # Remove prefixos de IA e limpa espaços
    texto_limpo = re.sub(r'^(System|Assistant|User|AI|Human|RAG|Resposta):\s*', '', texto, flags=re.IGNORECASE).strip()

    # --- FIX: Remove a frase de "não encontrado" se houver uma resposta antes dela ---
    fallback_pattern = r"Não encontrei informações suficientes nos documentos da área.*para responder a esta pergunta com precisão\."
    if len(texto_limpo) > 150:
        texto_limpo = re.sub(fallback_pattern, "", texto_limpo, flags=re.DOTALL | re.IGNORECASE).strip()

    return texto_limpo
# ==============================================================================
# 2. GERADOR DE TÍTULOS (IA BLINDADA - ASYNC)
# ==============================================================================

async def _gerar_topico_documento_async(texto_bruto: str, nome_arquivo_original: str = None) -> str:
    """Usa o LLM para dar um nome descritivo ao conteúdo do arquivo (Versão Async Otimizada)."""
    # Aumentamos a amostra para 2000 caracteres para dar mais contexto
    amostra = texto_bruto[:2000].replace("\n", " ").strip()
    
    # Se o texto for muito curto ou irrelevante, usamos o nome do arquivo
    if len(amostra) < 50 and nome_arquivo_original:
        return nome_arquivo_original.replace("_", " ").replace(".pdf", "").title()[:60]

    system_instruction = """ATENÇÃO: Você é um bibliotecário acadêmico da UCDB.
    Sua tarefa é ler o trecho de um documento e criar um Título Curto e Profissional (3 a 6 palavras).
    REGRAS:
    1. Responda APENAS com o título.
    2. NUNCA use "Documento Processado", "Sem Título" ou frases genéricas.
    3. Se o texto for jurídico, use o número da lei ou decreto se aparecer.
    4. Se for acadêmico, use o tema central (ex: Cálculo Diferencial, História do Brasil).
    5. Máximo 60 caracteres."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", "TEXTO PARA ANÁLISE:\n---\n{texto_amostra}\n---\n\nQUAL O TEMA CENTRAL DESTE TEXTO?")
    ])

    chain = prompt | get_cached_llm() | StrOutputParser()

    try:
        raw_titulo = await chain.ainvoke({"texto_amostra": amostra})
        titulo = raw_titulo.strip().replace('"', '').replace("'", "").replace("*", "").replace("#", "")
        titulo = re.sub(r'^(Título|Tópico|Assunto|Tema|Title|Topic|Resposta):\s*', '', titulo, flags=re.IGNORECASE)
        
        # Validação final: se a IA retornar algo inútil ou vazio, usamos o nome do arquivo
        invalid_titles = ["documento processado", "sem título", "desconhecido", "tópico central", "não identificado"]
        if not titulo or any(it in titulo.lower() for it in invalid_titles):
            if nome_arquivo_original:
                return nome_arquivo_original.replace("_", " ").replace(".pdf", "").title()[:60]
            return "Documento Acadêmico"
            
        return titulo.strip()[:60]
    except Exception as e:
        logger.error(f"Erro ao gerar título async: {e}")
        if nome_arquivo_original:
            return nome_arquivo_original.replace("_", " ").replace(".pdf", "").title()[:60]
        return "Documento Acadêmico"

# ==============================================================================
# 3. INGESTÃO GLOBAL BLINDADA (VARREDURA COMPLETA - ASYNC)
# ==============================================================================

async def atualizar_base_de_conhecimento_async():
    logger.info("🔄 Iniciando sincronização INTELIGENTE global (ASYNC)...")
    
    if not os.path.exists(settings.pdf_path):
        os.makedirs(settings.pdf_path)
        return
    
    # [DESATIVADO] A quebra de PDF no disco foi removida para poupar SSD/RAM
    # from quebrapdf import quebrar_pdf_por_capitulos
    # await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: quebrar_pdf_por_capitulos(settings.pdf_path))

    emb_model = get_cached_embeddings()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)

    itens = os.listdir(settings.pdf_path)
    areas = [d for d in itens if os.path.isdir(os.path.join(settings.pdf_path, d))]
    
    formatos_suportados = ('.pdf', '.docx', '.txt')
    if any(f.lower().endswith(formatos_suportados) for f in itens): areas.append("Geral")

    for nome_pasta in areas:
        area_key = _normalizar_nome_area(nome_pasta)
        origem = settings.pdf_path if nome_pasta == "Geral" else os.path.join(settings.pdf_path, nome_pasta)
        
        arquivos = [f for f in os.listdir(origem) if f.lower().endswith(formatos_suportados)]
        if not arquivos: continue

        caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
        os.makedirs(caminho_indice, exist_ok=True)
        manifesto = carregar_manifesto(caminho_indice)
        
        pendentes = [arq for arq in arquivos if arq not in manifesto or "title" not in manifesto[arq]]
        if not pendentes: continue

        logger.info(f"🚀 Área '{nome_pasta}': Atualizando {len(pendentes)} arquivos.")
        docs_para_indexar = []
        
        for i, arq in enumerate(pendentes, 1):
            try:
                logger.info(f"🧠 [{i}/{len(pendentes)}] Analisando: {arq}")
                loader = _get_loader(os.path.join(origem, arq))
                if not loader: continue
                
                full_docs = await asyncio.get_event_loop().run_in_executor(_io_executor, loader.load)
                if not full_docs: continue

                texto_para_titulo = " ".join([d.page_content for d in full_docs[:3]])
                titulo_gerado = await _gerar_topico_documento_async(texto_para_titulo, arq)

                for d in full_docs:
                    d.metadata.update({"source": arq, "area": nome_pasta, "topic": titulo_gerado})
                
                chunks = text_splitter.split_documents(full_docs)
                docs_para_indexar.extend(chunks)
                
                manifesto[arq] = {
                    "status": "indexed",
                    "title": titulo_gerado,
                    "pages_indexed": len(full_docs),
                    "last_updated": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"❌ Erro ao processar {arq}: {e}")

        if docs_para_indexar:
            def _save_faiss():
                if os.path.exists(os.path.join(caminho_indice, "index.faiss")):
                    vs = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
                    vs.add_documents(docs_para_indexar) 
                    vs.save_local(caminho_indice)
                else:
                    vs = FAISS.from_documents(docs_para_indexar, emb_model)
                    vs.save_local(caminho_indice)

            await asyncio.get_event_loop().run_in_executor(_io_executor, _save_faiss)
            salvar_manifesto(caminho_indice, manifesto)
            _vs_cache.delete(caminho_indice)

import networkx as nx
import pickle

class LightweightGraphRAG:
    """Gerencia relacionamentos entre entidades usando NetworkX (In-Memory)."""
    def __init__(self, index_path: str):
        self.index_path = index_path
        self.graph_path = os.path.join(index_path, "graph.pkl")
        self.graph = nx.Graph()
        self._load()

    def _load(self):
        if os.path.exists(self.graph_path):
            try:
                with open(self.graph_path, "rb") as f:
                    self.graph = pickle.load(f)
            except: self.graph = nx.Graph()

    def save(self):
        with open(self.graph_path, "wb") as f:
            pickle.dump(self.graph, f)

    async def extract_entities_and_relations(self, text: str):
        """Usa o LLM para extrair entidades e relações de um chunk."""
        # Filtro de palavras-chave para candidatos (Economiza chamadas ao LLM)
        amostra = text[:1500]
        
        system_instruction = """Você é um extrator de grafos de conhecimento acadêmico.
        Sua tarefa é identificar Entidades (Conceitos, Modelos, Leis) e como elas se relacionam.
        Responda APENAS no formato: Entidade1 | Relacao | Entidade2. Máximo 5 relações."""
        
        from app.core.llm import get_llm
        llm = get_llm()
        
        try:
            # Para ser performático, só extraímos se o texto for denso
            if len(text.strip()) < 200: return
            
            # Chamada ao LLM para extração
            response = await llm.ainvoke(f"{system_instruction}\n\nTexto: {amostra}")
            content = response.content if hasattr(response, 'content') else str(response)
            
            for line in content.split("\n"):
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) == 3:
                        self.add_relation(parts[0], parts[2], parts[1])
        except Exception as e:
            logger.error(f"Erro na extração de grafo: {e}")

    def add_relation(self, u, v, relation_type="related"):
        self.graph.add_edge(u, v, type=relation_type)

    def get_context(self, entities: List[str], depth=1) -> str:
        """Busca nós vizinhos para expandir o contexto."""
        context_nodes = set()
        for entity in entities:
            if entity in self.graph:
                context_nodes.add(entity)
                neighbors = list(self.graph.neighbors(entity))
                context_nodes.update(neighbors[:5]) # Limita vizinhos
        
        if not context_nodes: return ""
        return "Relacionamentos encontrados: " + ", ".join(context_nodes)

# ==============================================================================
# 3.1. INGESTÃO SELETIVA (ASYNC)
# ==============================================================================

from langchain_core.documents import Document

import fitz  # PyMuPDF

def _carregar_pdf_eficiente(file_path: str) -> List[Document]:
    """Lê o PDF usando PyMuPDF (fitz) para alta performance."""
    docs = []
    try:
        doc = fitz.open(file_path)
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                docs.append(Document(
                    page_content=text,
                    metadata={
                        "source": os.path.basename(file_path), 
                        "page": i + 1,
                        "total_pages": len(doc)
                    }
                ))
        doc.close()
    except Exception as e:
        logger.error(f"Erro ao ler PDF com PyMuPDF {file_path}: {e}")
        # Fallback para pypdf se fitz falhar por algum motivo raro
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    docs.append(Document(
                        page_content=text,
                        metadata={"source": os.path.basename(file_path), "page": i + 1}
                    ))
        except: pass
    return docs

def _get_loader_data(file_path: str) -> List[Document]:
    """Retorna os documentos extraídos de forma eficiente."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return _carregar_pdf_eficiente(file_path)
    elif ext == '.docx':
        from langchain_community.document_loaders import Docx2txtLoader
        return Docx2txtLoader(file_path).load()
    elif ext == '.txt':
        from langchain_community.document_loaders import TextLoader
        return TextLoader(file_path, encoding='utf-8').load()
    return []

@monitor_perf("Vetorização de Área")
async def processar_area_especifica_async(area: str, caminhos_arquivos: List[str], user_id: str = None, force_reindex: bool = False):
    """
    Versão OTIMIZADA: 
    - Sliding Window (Text Splitter com Overlap)
    - PyMuPDF para extração ultra-rápida.
    - GraphRAG (NetworkX) integrado para relacionamentos.
    """
    logger.info(f"🔄 Iniciando processamento otimizado para: {area}")
    
    area_key = _normalizar_nome_area(area)
    caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
    os.makedirs(caminho_indice, exist_ok=True)

    emb_model = get_cached_embeddings()
    # SLIDING WINDOW: Chunk overlap garante continuidade do contexto
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE, 
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    manifesto = carregar_manifesto(caminho_indice)
    graph_manager = LightweightGraphRAG(caminho_indice)
    
    from quebrapdf import quebrar_arquivo_unico
    
    # 1. Primeiro, processamos a quebra dos arquivos se necessário (em background)
    arquivos_finais = []
    if caminhos_arquivos:
        for arq_path in caminhos_arquivos:
            if arq_path.lower().endswith(".pdf"):
                if user_id:
                    await manager.send_personal_message({
                        "type": "processing_warning", 
                        "message": f"Analisando capítulos de {os.path.basename(arq_path)}..."
                    }, user_id)
                
                logger.info(f"✂️ Verificando capítulos para: {os.path.basename(arq_path)}")
                partes = await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: quebrar_arquivo_unico(arq_path))
                
                # Se não gerou partes novas, usa o arquivo original
                if not partes:
                    arquivos_finais.append(arq_path)
                else:
                    arquivos_finais.extend(partes)
            else:
                arquivos_finais.append(arq_path)
    else:
        # Se caminhos_arquivos for None, carregamos todos da pasta física para reconstruir
        area_safe = _normalizar_nome_area(area)
        base_dir = Path(settings.pdf_path) / area_safe
        if base_dir.exists():
            arquivos_finais = [str(f) for f in base_dir.glob("*") if f.suffix.lower() in ['.pdf', '.docx', '.txt']]

    if user_id and len(arquivos_finais) > 5:
        await manager.send_personal_message({
            "type": "processing_warning", 
            "message": f"Iniciando vetorização de {len(arquivos_finais)} partes..."
        }, user_id)

    # 2. Carrega o índice FAISS
    vectorstore = None
    if os.path.exists(os.path.join(caminho_indice, "index.faiss")):
        try:
            vectorstore = await asyncio.get_event_loop().run_in_executor(
                _io_executor, 
                lambda: FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
            )
        except Exception as e:
            logger.error(f"Erro ao carregar índice FAISS: {e}")

    # 3. Vetorização sequencial para poupar RAM
    for arq_path in arquivos_finais:
        nome_arquivo = os.path.basename(arq_path)
        
        # Logamos se estamos pulando ou processando
        if not force_reindex and nome_arquivo in manifesto and manifesto[nome_arquivo].get("status") == "indexed":
            logger.info(f"⏭️ Pulando {nome_arquivo} (já indexado).")
            continue

        logger.info(f"🧠 Analisando texto: {nome_arquivo}")
        
        full_docs = await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: _get_loader_data(arq_path))
        if not full_docs:
            logger.warning(f"⚠️ Nenhum texto extraído de {nome_arquivo}. O PDF pode ser apenas imagem.")
            continue

        # Título inteligente baseado no conteúdo
        texto_para_titulo = " ".join([d.page_content for d in full_docs[:2]])
        titulo_gerado = await _gerar_topico_documento_async(texto_para_titulo, nome_arquivo)

        # Extração de título de capítulo se for parte
        if "_parte_" in nome_arquivo:
            try:
                parts = nome_arquivo.split("_")
                if len(parts) > 4:
                    titulo_capitulo = " ".join(parts[3:]).replace(".pdf", "").replace("_", " ")
                    titulo_gerado = f"{titulo_capitulo} ({titulo_gerado})"
            except: pass

        for d in full_docs:
            d.metadata.update({"source": nome_arquivo, "area": area, "topic": titulo_gerado})
        
        chunks = text_splitter.split_documents(full_docs)
        del full_docs # Libera RAM
        
        if chunks:
            logger.info(f"🚀 Enviando {len(chunks)} trechos para a GPU (Embedding & Graph)...")
            
            # Extração de Grafos (GraphRAG) em paralelo leve
            for chunk in chunks[:10]: # Limitamos aos primeiros chunks para não travar muito a ingestão
                await graph_manager.extract_entities_and_relations(chunk.page_content)

            def _add_to_vs(vs, docs):
                if vs:
                    vs.add_documents(docs)
                    return vs
                else:
                    return FAISS.from_documents(docs, emb_model)

            vectorstore = await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: _add_to_vs(vectorstore, chunks))
            
            manifesto[nome_arquivo] = {
                "status": "indexed", "title": titulo_gerado,
                "chunks": len(chunks),
                "last_updated": datetime.now().isoformat()
            }
            logger.info(f"✅ {nome_arquivo} indexado com sucesso.")
        else:
            logger.warning(f"⚠️ {nome_arquivo} gerou 0 trechos após divisão.")

    # 4. Salva o índice final e o grafo
    if vectorstore:
        logger.info(f"💾 Salvando índice final e grafo da área {area}...")
        await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: vectorstore.save_local(caminho_indice))
        graph_manager.save()
        salvar_manifesto(caminho_indice, manifesto)
        _vs_cache.delete(caminho_indice)
        logger.info(f"🎉 Processamento concluído!")

    if user_id:
        await manager.send_personal_message({
            "type": "processing_complete", "area": area,
            "message": f"A base '{area}' foi atualizada com sucesso!"
        }, user_id)
# ==============================================================================
# 3.2. GERENCIADOR DE PERSONAS (MOTOR DE RACIOCÍNIO ACADÊMICO)
# ==============================================================================

def _obter_prompt_persona(area: str) -> str:
    """
    Retorna um prompt direto e objetivo focado em precisão técnica.
    """
    area_display = area.capitalize() if area else "Geral"

    return f"""Você é o Assistente Especialista da UCDB.
Sua missão é responder perguntas de forma **direta, técnica e sem rodeios**, baseando-se apenas nos documentos fornecidos.

### 🛠️ REGRAS DE OURO:
1. **Objetividade Máxima**: Vá direto ao ponto. Evite introduções longas ou conclusões repetitivas.
2. **Fidelidade**: Use apenas o <contexto_oficial>. Se a informação não estiver lá, diga apenas: "Não encontrei informações suficientes na base de {area_display}."
3. **Sem Citações no Texto**: Não escreva nomes de arquivos ou fontes no corpo da resposta.
4. **Formatação Técnica**: 
   - Use **negrito** para termos cruciais.
   - Use listas (bullets) para clareza.
   - **Matemática e Quóruns**: SEMPRE use LaTeX com `$` para frações e números técnicos. **Nunca** escreva "3/5", escreva obrigatoriamente `$\frac{3}{5}$`. 
   - **Exemplo**: "O quórum é de $\frac{3}{5}$ dos membros."

---

<contexto_oficial>
{{context}}
</contexto_oficial>

Responda agora de forma clara e concisa:"""

# ==============================================================================
# 5. RAG CHAIN ASYNC (OTIMIZADA PARA PERFORMANCE)
# ==============================================================================

@monitor_perf("Criação de RAG Chain")
async def get_rag_chain_async(area: str = "Geral"):
    """
    Versão assíncrona do RAG Chain. Carrega o índice FAISS em uma thread separada
    para não travar o loop de eventos do FastAPI.
    """
    # 1. Normalização inteligente da área
    if not area or area.lower().strip() == "geral":
        area_key = "geral"
    else:
        area_key = _normalizar_nome_area(area)

    caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")

    # Fallback: Se não existe index_area, tenta o index_geral (se a área atual não for geral)
    if not os.path.exists(caminho_indice):
        if area_key != "geral":
            logger.warning(f"Índice '{area_key}' não encontrado. Tentando fallback 'geral'...")
            area_key = "geral"
            caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
        
        # Verifica se o fallback 'geral' (ou a área original se for geral) existe
        if not os.path.exists(caminho_indice):
            logger.error(f"Nenhum índice encontrado para '{area_key}'.")
            return None

    # Tenta obter do cache
    vectorstore = _vs_cache.get(caminho_indice)

    if not vectorstore:
        emb_model = get_cached_embeddings()
        # Carrega o índice FAISS em uma thread para não travar o loop async
        try:
            vectorstore = await asyncio.get_event_loop().run_in_executor(
                _io_executor,
                lambda: FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
            )
            _vs_cache.set(caminho_indice, vectorstore)
        except Exception as e:
            logger.error(f"Erro ao carregar índice FAISS {area_key}: {e}")
            return None

    retriever = vectorstore.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K * 2}) # Pega o dobro para reranking

    # --- COMPONENTE GRAPHRAG (Lightweight) ---
    graph_manager = LightweightGraphRAG(caminho_indice)

    async def get_graph_context(input_data: dict) -> str:
        question = input_data["question"]
        # Extraímos entidades simples da pergunta (keywords)
        keywords = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]{2,}\b', question)
        if not keywords:
            keywords = question.split()[-3:]

        graph_data = graph_manager.get_context(keywords)
        return f"\n[RELAÇÕES ENCONTRADAS]: {graph_data}\n" if graph_data else ""

    # LLM Bindado com tokens de parada
    llm = get_cached_llm().bind(stop=["Human:", "User:", "Question:", "System:", "<|im_end|>", "<|eot_id|>"])

    system_msg = _obter_prompt_persona(area)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{question}")
    ])

    # LCEL Chain com suporte a Grafo + Vetores
    chain = (
        RunnableParallel({
            "docs_raw": itemgetter("question") | retriever,
            "graph_context": get_graph_context,
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        })
        .assign(docs=lambda x: _rerank_documents(x["question"], x["docs_raw"]))
        .assign(answer=(
            RunnablePassthrough.assign(
                context=lambda x: f"{x['graph_context']}\n{format_docs(x['docs'])}"
            )
            | prompt
            | llm
            | StrOutputParser()
            | RunnableLambda(_sanitizar_resposta)
        ))
        .pick(["answer", "docs"])
    )

    return chain | RunnableLambda(lambda x: {"answer": x["answer"], "source_documents": x["docs"]})