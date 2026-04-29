import os
import json
import re
import asyncio
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

def _carregar_manifesto(caminho_indice: str) -> dict:
    p = os.path.join(caminho_indice, "manifest.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def _salvar_manifesto(caminho_indice: str, dados: dict):
    with open(os.path.join(caminho_indice, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def format_docs(docs):
    return "\n\n".join(f"[Fonte: {d.metadata.get('source', 'Doc')}] {d.page_content}" for d in docs)

@monitor_perf("Reranking de Documentos")
def _rerank_documents(question: str, docs: List[Any]) -> List[Any]:
    """
    Otimização de Reranking: Filtra e ordena documentos para garantir alta relevância.
    Prioriza documentos com maior densidade de palavras-chave da pergunta.
    """
    if not docs: return []
    
    # 1. Filtro básico de qualidade
    docs = [d for d in docs if len(d.page_content.strip()) > 30]
    
    if not question: return docs[:settings.RETRIEVAL_K]
    
    # 2. Reranking simplificado por frequência de termos (BM25 'light')
    words = set(re.findall(r'\w+', question.lower()))
    
    scored_docs = []
    for d in docs:
        content_lower = d.page_content.lower()
        score = sum(1 for w in words if w in content_lower)
        # Bônus se as palavras aparecerem no tópico/título
        topic = d.metadata.get("topic", "").lower()
        score += sum(2 for w in words if w in topic)
        scored_docs.append((score, d))
    
    # Ordena pelo score (maior primeiro)
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    return [d for score, d in scored_docs if score > 0][:settings.RETRIEVAL_K]

def _sanitizar_resposta(texto: str) -> str:
    if not texto: return ""
    texto_limpo = re.sub(r'^(System|Assistant|User|AI|Human|RAG):\s*', '', texto, flags=re.IGNORECASE).strip()
    texto_limpo = re.sub(r'^[.\-,\s\n]+', '', texto_limpo)
    return texto_limpo

# ==============================================================================
# 2. GERADOR DE TÍTULOS (IA BLINDADA - ASYNC)
# ==============================================================================

async def _gerar_topico_documento_async(texto_bruto: str) -> str:
    """Usa o LLM para dar um nome descritivo ao conteúdo do arquivo (Versão Async)."""
    amostra = texto_bruto[:1000].replace("\n", " ").strip()
    
    system_instruction = """ATENÇÃO: Você é uma API de extração de metadados. 
    Sua ÚNICA função é ler o texto e extrair um Tópico Central de 3 a 6 palavras.
    REGRAS: 1. APENAS o título. 2. Sem 'O texto fala sobre'. 3. Máximo 6 palavras."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", "TEXTO PARA ANÁLISE:\n---\n{texto_amostra}\n---\n\nTÓPICO CENTRAL:")
    ])

    chain = prompt | get_cached_llm() | StrOutputParser()

    try:
        raw_titulo = await chain.ainvoke({"texto_amostra": amostra})
        titulo = raw_titulo.strip().replace('"', '').replace("'", "").replace("*", "").replace("#", "")
        titulo = re.sub(r'^(Título|Tópico|Assunto|Tema|Title|Topic):\s*', '', titulo, flags=re.IGNORECASE)
        return titulo.strip()[:60]
    except Exception as e:
        logger.error(f"Erro ao gerar título async: {e}")
        return "Documento Processado"

# ==============================================================================
# 3. INGESTÃO GLOBAL BLINDADA (VARREDURA COMPLETA - ASYNC)
# ==============================================================================

async def atualizar_base_de_conhecimento_async():
    logger.info("🔄 Iniciando sincronização INTELIGENTE global (ASYNC)...")
    
    if not os.path.exists(settings.pdf_path):
        os.makedirs(settings.pdf_path)
        return
    
    from quebrapdf import quebrar_pdf_por_capitulos
    # Offload heavy PDF splitting to thread
    await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: quebrar_pdf_por_capitulos(settings.pdf_path))

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
        manifesto = _carregar_manifesto(caminho_indice)
        
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
                titulo_gerado = await _gerar_topico_documento_async(texto_para_titulo)

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
            _salvar_manifesto(caminho_indice, manifesto)
            _vs_cache.delete(caminho_indice)

# ==============================================================================
# 3.1. INGESTÃO SELETIVA (ASYNC)
# ==============================================================================

@monitor_perf("Vetorização de Área")
async def processar_area_especifica_async(area: str, caminhos_arquivos: List[str], user_id: str = None):
    """
    Recebe os caminhos físicos dos arquivos recém-salvos e atualiza APENAS o 
    vectorstore e o manifesto correspondentes a essa área de conhecimento.
    Utiliza indexação incremental para poupar memória RAM.
    """
    logger.info(f"🔄 Processando {len(caminhos_arquivos)} arquivos para a área: {area} (ASYNC)")
    
    area_key = _normalizar_nome_area(area)
    caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
    os.makedirs(caminho_indice, exist_ok=True)

    emb_model = get_cached_embeddings()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
    
    manifesto = _carregar_manifesto(caminho_indice)
    
    for arq_path in caminhos_arquivos:
        nome_arquivo = os.path.basename(arq_path)
        try:
            # 1. Verificação de Imagem (Leve)
            if arq_path.lower().endswith('.pdf') and _is_pdf_image_only(arq_path):
                logger.warning(f"⚠️ O arquivo {nome_arquivo} parece ser apenas imagem.")
                if user_id:
                    await manager.send_personal_message({
                        "type": "processing_warning",
                        "message": f"O arquivo '{nome_arquivo}' parece ser uma imagem digitalizada."
                    }, user_id)

            # 2. Carregamento e Fatiamento
            loader = _get_loader(arq_path)
            if not loader: continue
            full_docs = await asyncio.get_event_loop().run_in_executor(_io_executor, loader.load)
            if not full_docs: continue
            
            # 3. Metadados e Títulos
            texto_para_titulo = " ".join([d.page_content for d in full_docs[:3]])
            titulo_gerado = await _gerar_topico_documento_async(texto_para_titulo)
            
            for d in full_docs:
                d.metadata.update({"source": nome_arquivo, "area": area, "topic": titulo_gerado})
                
            chunks = text_splitter.split_documents(full_docs)
            
            # 4. Indexação Incremental (Arquivo por Arquivo) para não explodir a RAM
            def _update_faiss_incremental(docs):
                indice_faiss_path = os.path.join(caminho_indice, "index.faiss")
                if os.path.exists(indice_faiss_path):
                    vs = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
                    vs.add_documents(docs)
                    vs.save_local(caminho_indice)
                else:
                    vs = FAISS.from_documents(docs, emb_model)
                    vs.save_local(caminho_indice)

            await asyncio.get_event_loop().run_in_executor(_io_executor, lambda: _update_faiss_incremental(chunks))
            
            # 5. Atualiza Manifesto
            manifesto[nome_arquivo] = {
                "status": "indexed", "title": titulo_gerado,
                "pages_indexed": len(full_docs), "last_updated": datetime.now().isoformat() 
            }
            _salvar_manifesto(caminho_indice, manifesto)
            
            # Limpa referências para o GC
            del full_docs
            del chunks
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar {nome_arquivo}: {e}")
            
    _vs_cache.delete(caminho_indice)
    if user_id:
        await manager.send_personal_message({
            "type": "processing_complete", "area": area,
            "message": f"Vetorização de {len(caminhos_arquivos)} arquivos concluída!"
        }, user_id)
# ==============================================================================
# 3.2. GERENCIADOR DE PERSONAS (PROMPTS DINÂMICOS)
# ==============================================================================

def _obter_prompt_persona(area: str) -> str:
    """Retorna o prompt do sistema (persona) adequado para a área solicitada."""
    area_normalizada = area.lower().strip()
    
    # 1. PERSONA: DIREITO
    if "direito" in area_normalizada:
        return """Você é um Professor e Auditor Jurídico da UCDB, rigoroso e literal.
Sua ÚNICA fonte de conhecimento são as leis, doutrinas e jurisprudências contidas nas tags <documentos>.

<documentos>
{context}
</documentos>

REGRAS DE RESPOSTA (DIREITO):
1. Baseie-se EXCLUSIVAMENTE nas leis, jurisprudências e doutrinas contidas nas tags acima.
2. Se o texto fornecer uma explicação doutrinária ou didática, use-a para formular uma resposta clara.
3. Sempre cite o artigo de lei ou o nome do documento/autor em sua resposta.
4. Se o contexto não trouxer informações suficientes, responda EXATAMENTE: "Não encontrei base legal ou doutrinária nos documentos disponibilizados."
5. NUNCA utilize conhecimento prévio ou invente informações jurídicas fora das tags."""

    # 2. PERSONA: ENGENHARIA E ARQUITETURA
    elif "engenharia" in area_normalizada or "arquitetura" in area_normalizada:
        return """Você é um Professor de Engenharia da UCDB, pragmático, matemático e focado em normas.
Sua base de conhecimento são as normas técnicas, manuais e cálculos contidos nas tags <documentos>.

<documentos>
{context}
</documentos>

REGRAS DE RESPOSTA (ENGENHARIA):
1. Forneça respostas diretas, estruturadas em passos lógicos ou tópicos.
2. SEMPRE utilize fórmulas matemáticas com MathJax.
   - Use APENAS $$ para blocos de fórmulas destacados (em linha própria). Ex: $$ FP = \frac{{P}}{{S}} $$
   - Use APENAS $ para fórmulas no meio do texto. Ex: $ P = V \cdot I $
   - PROIBIDO usar delimitadores como \[ \], \( \), [ ] ou ( ) para fórmulas.
3. Baseie-se APENAS nos manuais, cálculos e normas (ex: ABNT) das tags.
4. Se a pergunta envolver parâmetros de segurança ou fórmulas que não estão explícitas no documento, recuse a resposta informando: "Dados técnicos insuficientes nos documentos. Consulte a norma original."
5. NUNCA invente medidas, fatores de segurança ou cálculos."""

    # 3. PERSONA: TECNOLOGIA E COMPUTAÇÃO
    elif "tecnologia" in area_normalizada or "computacao" in area_normalizada or "sistemas" in area_normalizada:
        return """Você é um Especialista em Tecnologia e Computação da UCDB.
Utilize estritamente a documentação de software, arquitetura e trechos de código presentes nas tags <documentos>.

<documentos>
{context}
</documentos>

REGRAS DE RESPOSTA (TECNOLOGIA):
1. Baseie sua resposta na arquitetura e documentação fornecida nas tags.
2. Utilize LaTeX para representar qualquer notação matemática, complexidade de algoritmos (Big O) ou lógica formal.
   - Use $$ para blocos destacados e $ para inline.
3. Se o usuário pedir para resolver um erro, forneça a solução documentada passo a passo.
4. Se a tecnologia ou biblioteca mencionada não constar no contexto, avise: "Esta tecnologia não faz parte da documentação indexada atualmente."
5. Mantenha um tom lógico, focado na resolução do problema e em boas práticas de código."""

    # 4. PERSONA: SAÚDE (Enfermagem, Fisio, Vet, etc)
    elif "saude" in area_normalizada or "medicina" in area_normalizada or "enfermagem" in area_normalizada or "veterinaria" in area_normalizada:
        return """Você é um Professor da Área de Saúde da UCDB, extremamente cauteloso e científico.
Sua base de conhecimento são estritamente os protocolos clínicos e artigos das tags <documentos>.

<documentos>
{context}
</documentos>

REGRAS DE RESPOSTA (SAÚDE):
1. Baseie-se APENAS nas diretrizes documentadas fornecidas.
2. Utilize LaTeX para representar qualquer notação técnica ou química.
   - Use $$ para blocos destacados e $ para inline.
3. Você está PROIBIDO de prescrever tratamentos diagnósticos ou dar conselhos médicos diretos ao usuário como se fosse uma consulta.
4. Trate a resposta de forma acadêmica e científica.
5. Se a resposta não for encontrada, diga: "Não há diretriz clínica ou protocolo nos documentos fornecidos para esta condição." """

    # 5. PERSONA: GERAL (Fallback para outras áreas)
    else:
        return """Você é o Assistente Especialista da UCDB.
Sua ÚNICA fonte de verdade são os textos contidos entre as tags <documentos>.

<documentos>
{context}
</documentos>

REGRAS DE RESPOSTA:
1. Responda à pergunta baseando-se EXCLUSIVAMENTE nas informações contidas nas tags.
2. Utilize LaTeX para representar qualquer fórmula matemática ou notação técnica.
   - Use $$ para blocos destacados e $ para inline.
3. Seja claro, direto e educado.
4. Se a informação não estiver clara ou não existir no texto, responda: "Não encontrei essa informação nos documentos disponibilizados."
5. NUNCA invente dados ou utilize conhecimento externo."""

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

    # Fallback: Se não existe index_area, tenta o index_geral se a área for nula
    if not os.path.exists(caminho_indice):
        logger.warning(f"Índice não encontrado para a área: {area_key}. Tentando fallback 'geral'...")
        area_key = "geral"
        caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")

    if not os.path.exists(caminho_indice):
        logger.error(f"Nenhum índice encontrado (nem mesmo fallback 'geral').")
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

    retriever = vectorstore.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K})

    # LLM Bindado com tokens de parada
    llm = get_cached_llm().bind(stop=["Human:", "User:", "Question:", "System:", "<|im_end|>", "<|eot_id|>"])

    system_msg = _obter_prompt_persona(area)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{question}")
    ])

    chain = (
        RunnableParallel({
            "context": itemgetter("question") | retriever | RunnableLambda(lambda docs: _rerank_documents("", docs)),
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        })
        .assign(answer=(
            RunnablePassthrough.assign(context=lambda x: format_docs(x["context"]))
            | prompt
            | llm
            | StrOutputParser()
            | RunnableLambda(_sanitizar_resposta)
        ))
        .pick(["answer", "context"])
    )

    return chain | RunnableLambda(lambda x: {"answer": x["answer"], "source_documents": x["context"]})