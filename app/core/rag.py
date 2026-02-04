import os
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate

# --- CORREÇÃO CRÍTICA PARA LANGCHAIN v1.2.8+ ---
# As chains tradicionais foram movidas ou requerem imports específicos.
# Tentamos importar do pacote clássico ou do novo caminho de migração.
try:
    # Tenta o caminho novo/clássico para versões > 1.0
    from langchain_classic.chains import create_retrieval_chain
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
except ImportError:
    # Fallback para versões anteriores (0.3.x)
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain

from app.core.embeddings import get_embeddings
from app.core.llm import get_llm
from app.utils.logger import logger

_chains_cache = {}

SYSTEM_TEMPLATE = r"""
Você é um assistente virtual da UCDB (Universidade Católica Dom Bosco).
Sua função é auxiliar alunos e professores de forma acadêmica e precisa.
Você está atuando agora especificamente na área de: {area}.

DIRETRIZES DE RESPOSTA:
1. Use estritamente o contexto fornecido para responder.
2. Se a informação não estiver no contexto, informe que não encontrou detalhes nos materiais desta área.
3. Mantenha um tom profissional e prestativo.

REGRAS DE FORMATAÇÃO (MATHJAX):
- Para fórmulas matemáticas, use OBRIGATORIAMENTE LaTeX.
- Blocos: $$ E = mc^2 $$ (Dê espaço entre os cifrões e a fórmula)
- Inline: \( x^2 \)
- Exemplo complexo: $$ V = R \cdot I $$
- Nunca use formatação que quebre o renderizador.

Contexto:
{context}
"""

def carregar_indices():
    """Varre a pasta storage_indexes e carrega todos os bancos FAISS disponíveis."""
    global _chains_cache
    index_path = "storage_indexes"
    
    try:
        embeddings = get_embeddings()
        llm = get_llm()
    except Exception as e:
        logger.error(f"Erro ao inicializar LLM/Embeddings: {e}")
        return {}
    
    if not os.path.exists(index_path):
        logger.error(f"❌ Pasta {index_path} não encontrada. Execute ingest_multiplo.py primeiro.")
        return {}

    # 1. Prompt alinhado com a chave "input"
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_TEMPLATE),
        ("human", "{input}"),
    ])

    loaded_chains = {}
    
    for item in os.listdir(index_path):
        caminho_area = os.path.join(index_path, item)
        if os.path.isdir(caminho_area):
            if not item.startswith("index_") and "index" not in item:
                continue

            nome_area = item.replace("index_", "").lower()
            
            try:
                vectorstore = FAISS.load_local(
                    caminho_area, 
                    embeddings, 
                    allow_dangerous_deserialization=True
                )
                
                # Retrieve mais robusto
                retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
                
                # 2. Criação da Chain com ligação explícita do Contexto
                combine_docs_chain = create_stuff_documents_chain(
                    llm, 
                    prompt,
                    document_variable_name="context"  # <--- ISSO É CRUCIAL
                )
                
                # 3. Chain final que injeta 'context' automaticamente
                rag_chain = create_retrieval_chain(retriever, combine_docs_chain)
                
                loaded_chains[nome_area] = rag_chain
                logger.info(f"✅ Especialista em '{nome_area}' carregado.")
            except Exception as e:
                logger.error(f"❌ Falha ao carregar '{item}': {e}")

    _chains_cache = loaded_chains
    
    if loaded_chains:
        primeira_chave = next(iter(loaded_chains))
        _chains_cache["institucional"] = loaded_chains[primeira_chave]
        _chains_cache["geral"] = loaded_chains[primeira_chave]

    return _chains_cache