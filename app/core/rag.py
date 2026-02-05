import os
import json
from operator import itemgetter
from typing import List

from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.logger import logger
from app.core.config import settings
from app.core.embeddings import get_embeddings
from app.core.llm import get_llm

_vectorstores_cache = {}

# --- UTILITÁRIOS ---
def _normalizar_nome_area(nome_pasta: str) -> str:
    return nome_pasta.lower().strip().replace(" ", "_")

def _carregar_manifesto(caminho_indice: str) -> dict:
    p = os.path.join(caminho_indice, "manifest.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def _salvar_manifesto(caminho_indice: str, dados: dict):
    with open(os.path.join(caminho_indice, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def format_docs(docs):
    return "\n\n".join(f"[Fonte: {d.metadata.get('source', 'Doc')}] {d.page_content}" for d in docs)

# --- INGESTÃO BLINDADA ---
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
                
                # 1. Leitura e Split
                loader = PyPDFLoader(os.path.join(origem, arq))
                docs = loader.load()
                
                for d in docs:
                    d.metadata["source"] = arq
                    d.metadata["area"] = nome_pasta
                
                chunks = text_splitter.split_documents(docs)
                if not chunks: 
                    logger.warning(f"⚠️ Arquivo vazio ou ilegível: {arq}")
                    continue

                # 2. Geração de Embeddings e Salvamento
                # Usamos um try/except interno para garantir que falhas de rede
                # não corrompam o índice principal
                try:
                    if os.path.exists(os.path.join(caminho_indice, "index.faiss")):
                        vs_atual = FAISS.load_local(caminho_indice, emb_model, allow_dangerous_deserialization=True)
                        vs_atual.add_documents(chunks) # Se der erro aqui, ele não salva
                        vs_atual.save_local(caminho_indice)
                    else:
                        vs_novo = FAISS.from_documents(chunks, emb_model)
                        vs_novo.save_local(caminho_indice)
                    
                    # Só atualiza o manifesto se salvou com sucesso
                    manifesto[arq] = "indexed"
                    _salvar_manifesto(caminho_indice, manifesto)
                    logger.info(f"💾 {arq} salvo com sucesso.")
                    
                except Exception as index_err:
                    logger.error(f"❌ Erro ao gerar/salvar índice para {arq}. Ignorando arquivo. Detalhes: {index_err}")
                    # Não relança o erro, apenas pula este arquivo para o próximo

            except Exception as e:
                logger.error(f"❌ Erro geral em {arq}: {e}")

# --- RAG PIPELINE (MANTIDO IGUAL) ---
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

    def gerar_titulo_documento(texto_bruto: str) -> str:
    # Limitamos a 3000 chars para não estourar o contexto e ser rápido
        amostra = texto_bruto[:3000].replace("\n", " ").strip()
        
        prompt = f"""<|im_start|>system
    Você é um Classificador de Documentos Acadêmicos de alta precisão.
    Sua tarefa é ler um trecho de texto e retornar APENAS o nome da **Disciplina** e o **Tópico Principal**.

    REGRAS DE SAÍDA:
    1. Formato: [Grande Área] - [Tópico Específico]
    2. Use Título Capitalizado (Title Case).
    3. Máximo de 6 palavras.
    4. PROIBIDO escrever frases introdutórias ("O texto trata de...", "Título sugerido:").
    5. PROIBIDO usar aspas ou ponto final.

    EXEMPLOS (Input -> Output):
    Input: "A integral de Riemann é definida como o limite da soma..."
    Output: Cálculo Diferencial - Integrais

    Input: "A Constituição Federal de 1988 estabelece os direitos fundamentais..."
    Output: Direito Constitucional - Direitos Fundamentais

    Input: "O transistor BJT opera em três regiões: corte, saturação e ativa..."
    Output: Eletrônica Analógica - Transistores<|im_end|>
    <|im_start|>user
    Texto para classificar:
    "{amostra}"<|im_end|>
    <|im_start|>assistant
    """
        return prompt
    
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
        ))
        .pick(["answer", "context"])
    )
    
    return chain | RunnableLambda(lambda x: {"answer": x["answer"], "source_documents": x["context"]})