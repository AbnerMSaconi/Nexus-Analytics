import os
import json
import re  # <--- IMPORTANTE PARA O FILTRO
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
# 1. UTILITÁRIOS E FILTROS DE LIMPEZA
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
    """
    Filtro 'Lava-Jato': Remove alucinações de tags do sistema.
    Se a IA começar respondendo 'System: blabla', isso corta o 'System:'.
    """
    if not texto: return ""
    
    # 1. Remove prefixos de Chat (System:, AI:, Assistant:)
    # O regex ^ significa "apenas no começo da linha"
    texto_limpo = re.sub(r'^(System|Assistant|User|AI|Human|RAG):\s*', '', texto, flags=re.IGNORECASE).strip()
    
    # 2. Remove repetição do nome da área se vazar (ex: "em circuitos eletricos System:")
    # Remove qualquer coisa que pareça um cabeçalho vazado antes de uma quebra de linha
    if "System:" in texto_limpo:
        texto_limpo = texto_limpo.split("System:")[-1].strip()
        
    return texto_limpo

# ==============================================================================
# 2. CLASSIFICADOR DE CONTEÚDO
# ==============================================================================

def classificar_conteudo_pdf(texto_bruto: str) -> str:
    amostra = texto_bruto[:2000].replace("\n", " ").strip()
    
    system_instruction = """Você é um Classificador de Documentos Acadêmicos.
    Sua tarefa é ler um trecho e retornar APENAS: [Grande Área] - [Tópico Específico].
    
    REGRAS:
    1. Máximo 6 palavras.
    2. Sem aspas, sem pontos finais, sem introduções.
    3. Exemplo: Engenharia Civil - Estruturas
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", "Classifique: \"{texto_amostra}\"")
    ])

    chain = prompt | get_llm() | StrOutputParser()

    try:
        return chain.invoke({"texto_amostra": amostra}).strip()
    except Exception:
        return "Geral - Indefinido"

# ==============================================================================
# 3. INGESTÃO BLINDADA
# ==============================================================================

def atualizar_base_de_conhecimento():
    logger.info("🔄 Iniciando sincronização BLINDADA...")
    
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
        pendentes = set(arquivos) - set(manifesto.keys())

        if not pendentes: continue

        logger.info(f"🚀 Área '{nome_pasta}': {len(pendentes)} arquivos novos.")
        
        for i, arq in enumerate(pendentes, 1):
            try:
                logger.info(f"📄 [{i}/{len(pendentes)}] Processando: {arq}")
                loader = PyPDFLoader(os.path.join(origem, arq))
                docs = loader.load()
                
                for d in docs:
                    d.metadata["source"] = arq
                    d.metadata["area"] = nome_pasta
                
                chunks = text_splitter.split_documents(docs)
                if not chunks: 
                    logger.warning(f"⚠️ Arquivo vazio: {arq}")
                    continue

                try:
                    if os.path.exists(os.path.join(caminho_indice, "index.faiss")):
                        vs_atual = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
                        vs_atual.add_documents(chunks) 
                        vs_atual.save_local(caminho_indice)
                    else:
                        vs_novo = FAISS.from_documents(chunks, emb_model)
                        vs_novo.save_local(caminho_indice)
                    
                    manifesto[arq] = "indexed"
                    _salvar_manifesto(caminho_indice, manifesto)
                    logger.success(f"💾 {arq} salvo.")
                except Exception as index_err:
                    logger.error(f"❌ Erro ao salvar índice {arq}: {index_err}")

            except Exception as e:
                logger.error(f"❌ Erro geral {arq}: {e}")

# ==============================================================================
# 4. CHAT RAG (PIPELINE COM FILTRO)
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

    # Prompt Ajustado para evitar vazamento
    # Note que coloquei a variável {area_nome} dentro de colchetes para separar visualmente pro LLM
    system_msg = r"""Você é o Assistente Especialista da UCDB. Área de Foco: [{area_nome}].
    
    INSTRUÇÕES DE FORMATO (OBRIGATÓRIO):
    1. **Use Markdown**:
       - Comece SEMPRE com um Título Principal (use # Título).
       - Use subtítulos (##) para separar tópicos.
       - Use Listas com marcadores (-) ou numéricas (1.) para passos.
       - Use **Negrito** para termos importantes.
    
    2. **Matemática**:
       - Blocos: $$ E=mc^2 $$
       - Inline: $ x $ ou \( x \)

    3. **Conteúdo**:
       - Responda de forma didática e estruturada em parágrafos.
       - Baseie-se APENAS no contexto fornecido.
       - NÃO use prefixos como "System:" ou "AI:".

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
            "area_nome": lambda x: area.capitalize() if area else "Geral"
        })
        .assign(answer=(
            RunnablePassthrough.assign(context=lambda x: format_docs(x["context"]))
            | prompt
            | llm
            | StrOutputParser()
            | RunnableLambda(_sanitizar_resposta) # <--- O FILTRO ENTRA AQUI!
        ))
        .pick(["answer", "context"])
    )
    
    return chain | RunnableLambda(lambda x: {"answer": x["answer"], "source_documents": x["context"]})