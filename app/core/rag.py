# app/core/rag.py - Títulos Inteligentes e Interpretativos
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.utils.logger import logger
from app.core.config import settings
from app.core.embeddings import LlamaEmbeddings
from app.core.llm import LlamaServerLLM
import os
import json

# --- 1. GERAÇÃO DE TÍTULOS (O Cérebro do Curador) ---
def _gerar_titulo_para_documento(texto_documento: str, llm: LlamaServerLLM) -> str:
    # Prompt com "liberdade poética" para interpretar o assunto
    prompt = f"""<|im_start|>system
Você é um Curador de Conteúdo Acadêmico experiente.
Sua missão é analisar o texto bruto de um documento e identificar claramente a qual **Disciplina** ou **Tópico de Estudo** ele pertence.

Regras de Ouro:
1. NÃO apenas resuma o texto. INTERPRETE o assunto principal.
2. Ignore termos genéricos como "Introdução", "Capítulo 1", "Prefácio" ou nomes de autores.
3. Crie um título descritivo e elegante (3 a 6 palavras).
4. Se o texto for sobre "Diodos e Transistores", o título deve ser "Eletrônica Analógica - Semicondutores" ou similar.
5. Responda APENAS com o título final, sem aspas.<|im_end|>
<|im_start|>user
Amostra do Documento:
{texto_documento[:3500]}<|im_end|>
<|im_start|>assistant
"""
    try: 
        titulo = llm._call(prompt).strip()
        # Limpezas de segurança
        titulo = titulo.replace('"', '').replace("Título:", "").split('\n')[0]
        return titulo if len(titulo) > 3 else "Tópico Geral"
    except: return "Documento Não Identificado"

# --- 2. GERENCIAMENTO DE ARQUIVOS ---
def _carregar_manifesto(path):
    p = os.path.join(path, "manifest.json")
    if os.path.exists(p):
        with open(p, "r") as f: return json.load(f)
    return {}

def _salvar_manifesto(path, data):
    with open(os.path.join(path, "manifest.json"), "w") as f: json.dump(data, f, indent=4)

def _listar_pdfs(base):
    pdfs = []
    for r, d, f in os.walk(base):
        for file in f:
            if file.lower().endswith('.pdf'):
                pdfs.append(os.path.relpath(os.path.join(r, file), base))
    return pdfs

def _processar_novos(base, arquivos, llm):
    chunks, titulos = [], {}
    # Mantemos 1000 para o RAG ter contexto, a redução para 250 pode quebrar raciocínios
    splitter = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
    
    for arq in arquivos:
        try:
            loader = PyPDFLoader(os.path.join(base, arq))
            docs = loader.load()
            if docs:
                # MELHORIA: Pega as 3 primeiras páginas para garantir que passamos o conteúdo real
                # e não apenas a capa ou folha de rosto.
                paginas_iniciais = docs[:3]
                texto_contexto = "\n".join([p.page_content for p in paginas_iniciais])
                
                tit = _gerar_titulo_para_documento(texto_contexto, llm)
                titulos[arq] = tit
                
                for d in docs:
                    d.metadata['source'] = arq
                    d.metadata['titulo'] = tit
                chunks.extend(splitter.split_documents(docs))
                logger.info(f"📚 Identificado: {arq} -> '{tit}'")
        except Exception as e: logger.error(f"Erro em {arq}: {e}")
    return chunks, titulos

# --- 3. VECTORSTORE ---
def criar_vectorstore():
    if not os.path.exists(settings.pdf_path): os.makedirs(settings.pdf_path)
    if not os.path.exists(settings.vectorstore_path): os.makedirs(settings.vectorstore_path)
    
    pdfs = _listar_pdfs(settings.pdf_path)
    if not pdfs: return None
    
    emb = LlamaEmbeddings(settings.EMBEDDING_API_URL)
    llm = LlamaServerLLM()
    v_path = settings.vectorstore_path
    
    manifesto = _carregar_manifesto(v_path)
    novos = set(pdfs) - set(manifesto.keys())
    
    if os.path.exists(os.path.join(v_path, "index.faiss")):
        vs = FAISS.load_local(v_path, emb, allow_dangerous_deserialization=True)
        if novos:
            c, t = _processar_novos(settings.pdf_path, novos, llm)
            if c:
                vs.add_documents(c)
                vs.save_local(v_path)
                manifesto.update(t)
                _salvar_manifesto(v_path, manifesto)
        return vs
    
    c, t = _processar_novos(settings.pdf_path, pdfs, llm)
    if not c: return None
    vs = FAISS.from_documents(c, emb)
    vs.save_local(v_path)
    _salvar_manifesto(v_path, t)
    return vs

# --- 4. RAG CHAIN ---
def criar_rag_chain(vectorstore):
    llm = LlamaServerLLM()
    
    condense_template = """<|im_start|>system
Reescreva a pergunta do usuário para torná-la independente, resolvendo referências como "ele", "isso" com base no histórico.<|im_end|>
<|im_start|>user
Histórico:
{chat_history}

Pergunta: {question}<|im_end|>
<|im_start|>assistant
"""
    CONDENSE_PROMPT = PromptTemplate.from_template(condense_template)

    # UPDATED PROMPT FOR FORMULAS
    qa_template = """<|im_start|>system
Você é o UCDB-IA, assistente acadêmico especialista.

REGRAS DE OURO PARA O VISUAL (SIGA RIGOROSAMENTE):
1. **FÓRMULAS DEVEM TER DESTAQUE:**
   - NUNCA coloque fórmulas importantes na mesma linha do texto.
   - Pule uma linha, escreva a fórmula entre `$$`, e pule outra linha.
   - Formato Obrigatório:
     
     $$V = R \cdot I$$
     
2. **NÃO USE LISTAS PARA FÓRMULAS:**
   - Errado: "1. Lei de Ohm: $V=RI$"
   - Certo: 
     "1. Lei de Ohm:
     $$V = R \cdot I$$"

3. Use `$` (inline) APENAS para citar variáveis pequenas como "onde $V$ é tensão".
4. Responda de forma didática e estruturada em Markdown.<|im_end|>
5. Titulos sempre em negrito e pule de linha antes e depois.
<|im_start|>user
Contexto:
{context}

Pergunta:
{question}<|im_end|>
<|im_start|>assistant
"""
    QA_PROMPT = PromptTemplate(template=qa_template, input_variables=["context", "question"])

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K}),
        condense_question_prompt=CONDENSE_PROMPT,
        combine_docs_chain_kwargs={"prompt": QA_PROMPT},
        return_source_documents=True,
        verbose=True
    )
    return chain