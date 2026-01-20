"""
UCDB-IA | Núcleo de Processamento RAG com Inteligência de Classificação
Gere a indexação FAISS e categoriza materiais nas áreas institucionais.
"""
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

def _classificar_material_didatico(texto_base: str, llm: LlamaServerLLM) -> dict:
    """Classifica o PDF em uma área específica e gera um título curto."""
    prompt = """<|start_header_id|>system<|end_header_id|>
Você é um bibliotecário acadêmico especialista. Analise o fragmento do texto e retorne EXCLUSIVAMENTE um JSON:
{"titulo": "Nome Técnico Curto", "categoria": "Engenharias" ou "Direito" ou "Saúde" ou "Humanas"}
REGRA: Escolha a categoria que melhor se adapta ao tema técnico.<|eot_id|><|start_header_id|>user<|end_header_id|>
Texto: {texto}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
    
    try:
        resultado = llm._call(prompt.format(texto=texto_base[:3500]))
        # Limpeza para garantir parse do JSON
        json_str = resultado[resultado.find('{'):resultado.rfind('}')+1]
        return json.loads(json_str)
    except Exception:
        return {"titulo": "Material de Apoio", "categoria": "Humanas"}

def _gerenciar_manifesto(caminho: str, acao: str = "ler", dados: dict = None):
    arquivo_manifesto = os.path.join(caminho, "manifest.json")
    if acao == "ler":
        if os.path.exists(arquivo_manifesto):
            with open(arquivo_manifesto, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(arquivo_manifesto, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def criar_vectorstore():
    """Gere a base vetorial e organiza o repositório em blocos categorizados."""
    if not os.path.exists(settings.pdf_path) or not os.listdir(settings.pdf_path):
        return None

    motor_emb = LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)
    ia_auxiliar = LlamaServerLLM()
    caminho_vs = settings.vectorstore_path
    
    manifesto = _gerenciar_manifesto(caminho_vs, "ler")
    pdfs_atuais = [f for f in os.listdir(settings.pdf_path) if f.endswith(".pdf")]
    novos_chunks = []
    
    divisor = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)

    for pdf in pdfs_atuais:
        if pdf not in manifesto:
            try:
                carregador = PyPDFLoader(os.path.join(settings.pdf_path, pdf))
                paginas = carregador.load()
                classificacao = _classificar_material_didatico(paginas[0].page_content, ia_auxiliar)
                
                manifesto[pdf] = classificacao
                novos_chunks.extend(divisor.split_documents(paginas))
                logger.info(f"✔ {pdf} categorizado em {classificacao['categoria']}")
            except Exception as e:
                logger.error(f"✘ Falha ao indexar {pdf}: {e}")

    # Carrega ou Cria a base FAISS
    if os.path.exists(os.path.join(caminho_vs, "index.faiss")):
        vectorstore = FAISS.load_local(caminho_vs, motor_emb, allow_dangerous_deserialization=True)
        if novos_chunks:
            vectorstore.add_documents(novos_chunks)
            vectorstore.save_local(caminho_vs)
            _gerenciar_manifesto(caminho_vs, "salvar", manifesto)
        return vectorstore

    if novos_chunks:
        vectorstore = FAISS.from_documents(novos_chunks, motor_emb)
        vectorstore.save_local(caminho_vs)
        _gerenciar_manifesto(caminho_vs, "salvar", manifesto)
        return vectorstore
    return None

def criar_rag_chain(vectorstore):
    """Configura o motor de conversação com prompt institucional blindado."""
    llm = LlamaServerLLM()
    
    template_qa = """<|start_header_id|>system<|end_header_id|>
Você é o UCDB-IA, assistente oficial da universidade. Responda apenas com base no Contexto de Apoio.
1. Use Markdown (###, ####, *) para estrutura.
2. Use LaTeX ($f(x)$) para matemática.
3. Se não houver informação, responda: "Não localizei dados suficientes nos materiais disponíveis."
Finalize com: "Posso ajudar com mais algum detalhe?"<|eot_id|><|start_header_id|>user<|end_header_id|>

**Contexto de Apoio:**
{context}

---
**Dúvida do Aluno:**
{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    QA_PROMPT = PromptTemplate(template=template_qa, input_variables=["context", "question"])

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K}),
        combine_docs_chain_kwargs={"prompt": QA_PROMPT},
        return_source_documents=True
    )