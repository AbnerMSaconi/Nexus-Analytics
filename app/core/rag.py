import os
import json
import re
from operator import itemgetter
from typing import List, Dict, Any

# --- IMPORTS LANGCHAIN ---
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- IMPORTS DO PROJETO ---
from app.utils.logger import logger
from app.core.config import settings
from app.core.embeddings import get_embeddings
from app.core.llm import get_llm

_vectorstores_cache = {}

# ==============================================================================
# 1. UTILITÁRIOS
# ==============================================================================

def _normalizar_nome_area(nome_pasta: str) -> str:
    return nome_pasta.lower().strip().replace(" ", "_")

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

def _sanitizar_resposta(texto: str) -> str:
    if not texto: return ""
    texto_limpo = re.sub(r'^(System|Assistant|User|AI|Human|RAG):\s*', '', texto, flags=re.IGNORECASE).strip()
    texto_limpo = re.sub(r'^[.\-,\s\n]+', '', texto_limpo)
    return texto_limpo

# ==============================================================================
# 2. GERADOR DE TÍTULOS (IA BLINDADA)
# ==============================================================================

def _gerar_topico_documento(texto_bruto: str) -> str:
    """Usa o LLM para dar um nome descritivo ao conteúdo do arquivo."""
    
    # 1. Reduzimos a amostra e removemos quebras de linha
    amostra = texto_bruto[:1000].replace("\n", " ").strip()
    
    # 2. Prompt Engenharia Reversa
    system_instruction = """ATENÇÃO: Você é uma API de extração de metadados. 
    Sua ÚNICA função é ler o texto e extrair um Tópico Central de 3 a 6 palavras.
    
    REGRAS DE OURO:
    1. NÃO use listas, bullets ou explicações.
    2. NÃO inicie com "O texto fala sobre...".
    3. Retorne APENAS o título.
    
    Exemplo Entrada: "...O protocolo TCP/IP é a base da internet..."
    Exemplo Saída: Protocolo de Redes TCP/IP"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", "TEXTO PARA ANÁLISE:\n---\n{texto_amostra}\n---\n\nTÓPICO CENTRAL:")
    ])

    chain = prompt | get_llm() | StrOutputParser()

    try:
        raw_titulo = chain.invoke({"texto_amostra": amostra}).strip()
        
        # 3. Pós-Processamento Brutal (Python)
        titulo = raw_titulo.replace('"', '').replace("'", "").replace("*", "").replace("#", "")
        titulo = re.sub(r'^(Título|Tópico|Assunto|Tema|Title|Topic):\s*', '', titulo, flags=re.IGNORECASE)
        
        if "\n" in titulo:
            linhas = [l.strip() for l in titulo.split('\n') if l.strip()]
            titulo = min(linhas, key=len) if linhas else "Documento Processado"

        # 4. Corte de Segurança Final
        if len(titulo) > 60:
            palavras = titulo.split()
            if len(palavras) > 5:
                titulo = " ".join(palavras[:5])
            else:
                titulo = "Documento Acadêmico"

        return titulo.strip()

    except Exception as e:
        logger.error(f"Erro ao gerar título: {e}")
        return "Documento Processado"

# ==============================================================================
# 3. INGESTÃO GLOBAL BLINDADA (VARREDURA COMPLETA)
# ==============================================================================

def atualizar_base_de_conhecimento():
    logger.info("🔄 Iniciando sincronização INTELIGENTE global...")
    
    if not os.path.exists(settings.pdf_path):
        os.makedirs(settings.pdf_path)
        return

    emb_model = get_embeddings()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)

    itens = os.listdir(settings.pdf_path)
    areas = [d for d in itens if os.path.isdir(os.path.join(settings.pdf_path, d))]
    if any(f.endswith('.pdf') for f in itens): areas.append("Geral")

    for nome_pasta in areas:
        area_key = _normalizar_nome_area(nome_pasta)
        origem = settings.pdf_path if nome_pasta == "Geral" else os.path.join(settings.pdf_path, nome_pasta)
        
        if nome_pasta == "Geral":
            arquivos = [f for f in itens if f.endswith('.pdf')]
        else:
            arquivos = [f for f in os.listdir(origem) if f.lower().endswith('.pdf')]

        if not arquivos: continue

        caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
        if not os.path.exists(caminho_indice): os.makedirs(caminho_indice)

        manifesto = _carregar_manifesto(caminho_indice)
        
        pendentes = []
        for arq in arquivos:
            if arq not in manifesto or isinstance(manifesto[arq], str) or "title" not in manifesto[arq]:
                pendentes.append(arq)

        if not pendentes: continue

        logger.info(f"🚀 Área '{nome_pasta}': Atualizando {len(pendentes)} arquivos.")
        
        docs_para_indexar = []
        
        for i, arq in enumerate(pendentes, 1):
            try:
                logger.info(f"🧠 [{i}/{len(pendentes)}] Analisando: {arq}")
                loader = PyPDFLoader(os.path.join(origem, arq))
                full_docs = loader.load() 
                
                amostra_titulo = full_docs[:3] 
                texto_para_titulo = " ".join([d.page_content for d in amostra_titulo])
                titulo_gerado = _gerar_topico_documento(texto_para_titulo)
                logger.info(f"   🏷️ Título Gerado: {titulo_gerado}")

                for d in full_docs:
                    d.metadata["source"] = arq
                    d.metadata["area"] = nome_pasta
                    d.metadata["topic"] = titulo_gerado
                
                chunks = text_splitter.split_documents(full_docs)
                docs_para_indexar.extend(chunks)
                
                manifesto[arq] = {
                    "status": "indexed",
                    "title": titulo_gerado,
                    "pages_indexed": len(full_docs),
                    "last_updated": "now"
                }
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar {arq}: {e}")

        if docs_para_indexar:
            try:
                if os.path.exists(os.path.join(caminho_indice, "index.faiss")):
                    vs_atual = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
                    vs_atual.add_documents(docs_para_indexar) 
                    vs_atual.save_local(caminho_indice)
                else:
                    vs_novo = FAISS.from_documents(docs_para_indexar, emb_model)
                    vs_novo.save_local(caminho_indice)
                
                _salvar_manifesto(caminho_indice, manifesto)
                logger.success(f"💾 Índice '{area_key}' salvo com sucesso.")
            except Exception as index_err:
                logger.error(f"❌ Erro crítico ao salvar índice FAISS: {index_err}")

# ==============================================================================
# 3.1. INGESTÃO SELETIVA (APENAS UMA ÁREA E ARQUIVOS ESPECÍFICOS) - NOVO!
# ==============================================================================

def processar_area_especifica(area: str, caminhos_arquivos: List[str]):
    """
    Recebe os caminhos físicos dos arquivos recém-salvos e atualiza APENAS o 
    vectorstore e o manifesto correspondentes a essa área de conhecimento.
    """
    logger.info(f"🔄 Processando {len(caminhos_arquivos)} arquivos para a área: {area}")
    
    area_key = _normalizar_nome_area(area)
    caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
    
    if not os.path.exists(caminho_indice):
        os.makedirs(caminho_indice)

    emb_model = get_embeddings()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
    
    manifesto = _carregar_manifesto(caminho_indice)
    docs_para_indexar = []
    
    for arq_path in caminhos_arquivos:
        nome_arquivo = os.path.basename(arq_path)
        try:
            logger.info(f"🧠 Analisando arquivo específico: {nome_arquivo}")
            loader = PyPDFLoader(arq_path)
            full_docs = loader.load()
            
            if not full_docs:
                continue
            
            # Gera título com uma pequena amostra para economizar tokens
            amostra_titulo = full_docs[:3]
            texto_para_titulo = " ".join([d.page_content for d in amostra_titulo])
            titulo_gerado = _gerar_topico_documento(texto_para_titulo)
            
            logger.info(f"   🏷️ Título Gerado: {titulo_gerado}")

            # Adiciona metadados
            for d in full_docs:
                d.metadata["source"] = nome_arquivo
                d.metadata["area"] = area
                d.metadata["topic"] = titulo_gerado
                
            chunks = text_splitter.split_documents(full_docs)
            docs_para_indexar.extend(chunks)
            
            # Atualiza manifesto para exibição no frontend
            manifesto[nome_arquivo] = {
                "status": "indexed",
                "title": titulo_gerado,
                "pages_indexed": len(full_docs),
                "last_updated": "now" 
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar {nome_arquivo}: {e}")
            
    if docs_para_indexar:
        try:
            indice_faiss_path = os.path.join(caminho_indice, "index.faiss")
            if os.path.exists(indice_faiss_path):
                # Anexa aos vetores existentes
                vs_atual = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
                vs_atual.add_documents(docs_para_indexar)
                vs_atual.save_local(caminho_indice)
            else:
                # Cria a nova base do zero
                vs_novo = FAISS.from_documents(docs_para_indexar, emb_model)
                vs_novo.save_local(caminho_indice)
                
            _salvar_manifesto(caminho_indice, manifesto)
            logger.info(f"💾 Índice '{area_key}' atualizado/criado com sucesso via modal seletivo.")
            
            # Limpa o cache para forçar a recarga no próximo RAG
            global _vectorstores_cache
            if caminho_indice in _vectorstores_cache:
                del _vectorstores_cache[caminho_indice]
                
        except Exception as index_err:
            logger.error(f"❌ Erro crítico ao salvar índice FAISS na área específica: {index_err}")
            raise index_err

# ==============================================================================
# 4. CHAT RAG
# ==============================================================================

def get_rag_chain(area: str = "Geral"):
    global _vectorstores_cache
    
    area_key = _normalizar_nome_area(area) if area else "geral"
    caminho_indice = os.path.join(settings.vectorstore_path, f"index_{area_key}")
    
    if not os.path.exists(caminho_indice):
        possiveis = [d for d in os.listdir(settings.vectorstore_path) if d.startswith("index_")]
        if possiveis: caminho_indice = os.path.join(settings.vectorstore_path, possiveis[0])
        else: return None

    if caminho_indice not in _vectorstores_cache:
        emb_model = get_embeddings()
        _vectorstores_cache[caminho_indice] = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)

    vectorstore = _vectorstores_cache[caminho_indice]
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    llm = get_llm()

    system_msg = r"""Você é o Assistente Especialista da UCDB.
    Responda usando APENAS o contexto fornecido.
    Use Markdown para formatar (títulos, listas, negrito).
    Se houver fórmulas, use LaTeX: $$ x^2 $$.
    
    Contexto:"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("system", "CONTEXTO:\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])
    
    chain = (
        RunnableParallel({
            "context": itemgetter("question") | retriever,
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