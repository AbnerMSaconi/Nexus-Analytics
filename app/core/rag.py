"""
UCDB-IA | Núcleo RAG Multi-Área
Gera embeddings isolados para cada subpasta encontrada em /pdfs.
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
import shutil

def inicializar_bases_de_conhecimento():
    """
    Percorre cada subpasta em 'pdfs/', cria um índice FAISS exclusivo
    e salva em 'vectorstore/{nome_da_pasta}'.
    """
    if not os.path.exists(settings.pdf_path):
        os.makedirs(settings.pdf_path)
        return {}

    motor_emb = LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)
    
    # Lista apenas diretórios dentro de pdfs/ (ex: Engenharias, Direito)
    areas = [d for d in os.listdir(settings.pdf_path) 
             if os.path.isdir(os.path.join(settings.pdf_path, d))]
    
    motores_prontos = {}

    for area in areas:
        caminho_pdf_area = os.path.join(settings.pdf_path, area)
        caminho_faiss_area = os.path.join(settings.vectorstore_path, area)
        
        # Verifica se há PDFs novos ou se a base não existe
        precisa_reindexar = False
        if not os.path.exists(caminho_faiss_area):
            precisa_reindexar = True
        
        # (Lógica simples: Se a pasta vectorstore não existe, cria. 
        # Para produção, ideal seria verificar timestamps dos arquivos).
        
        if precisa_reindexar:
            logger.info(f"🔄 Indexando área: {area}...")
            docs_area = []
            arquivos = [f for f in os.listdir(caminho_pdf_area) if f.endswith(".pdf")]
            
            if not arquivos:
                continue

            for arq in arquivos:
                try:
                    loader = PyPDFLoader(os.path.join(caminho_pdf_area, arq))
                    # Adiciona metadados para saber a origem
                    docs = loader.load()
                    for d in docs:
                        d.metadata["area"] = area
                        d.metadata["source"] = arq
                    docs_area.extend(docs)
                except Exception as e:
                    logger.error(f"Erro ao ler {arq}: {e}")

            if docs_area:
                divisor = RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
                chunks = divisor.split_documents(docs_area)
                
                # Cria a base isolada
                vectorstore = FAISS.from_documents(chunks, motor_emb)
                vectorstore.save_local(caminho_faiss_area)
                logger.info(f"✅ Base '{area}' criada com sucesso!")
            else:
                logger.warning(f"Pasta {area} vazia ou sem PDFs válidos.")

    return True

def carregar_motor_especifico(area_alvo: str):
    """
    Carrega o índice FAISS específico da área solicitada (ex: 'Direito').
    Retorna a Chain RAG pronta para uso.
    """
    caminho_faiss = os.path.join(settings.vectorstore_path, area_alvo)
    
    if not os.path.exists(caminho_faiss):
        logger.warning(f"Base para '{area_alvo}' não encontrada.")
        return None

    motor_emb = LlamaEmbeddings(api_url=settings.EMBEDDING_API_URL)
    
    try:
        vectorstore = FAISS.load_local(caminho_faiss, motor_emb, allow_dangerous_deserialization=True)
        llm = LlamaServerLLM()
        
        template_qa = """<|start_header_id|>system<|end_header_id|>
Você é um especialista em {area}. Responda apenas com base no contexto abaixo.
Se não souber, diga que o material não cobre o assunto.
Use terminologia técnica adequada à área de {area}.<|eot_id|><|start_header_id|>user<|end_header_id|>

Contexto:
{context}

Pergunta:
{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

        QA_PROMPT = PromptTemplate(
            template=template_qa.format(area=area_alvo, context="{context}", question="{question}"),
            input_variables=["context", "question"]
        )

        return ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K}),
            combine_docs_chain_kwargs={"prompt": QA_PROMPT},
            return_source_documents=True
        )
    except Exception as e:
        logger.error(f"Erro ao carregar motor {area_alvo}: {e}")
        return None