import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain_community.llms import LlamaCpp

# Configurações
MODEL_PATH = "models/llama-3-8b.gguf" # Verifique se o nome do seu modelo está correto aqui
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
STORAGE_BASE_PATH = "storage_indexes"

# Variável Global para armazenar os índices carregados
loaded_indexes = {}

def carregar_indices():
    """
    Varre a pasta storage_indexes e carrega todos os bancos FAISS encontrados na memória.
    Retorna: Um dicionário {'engenharia': VectorStore, 'tecnologia': VectorStore, ...}
    """
    global loaded_indexes
    
    print("🔄 Carregando índices vetoriais...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL, model_kwargs={'trust_remote_code': True})
    
    if not os.path.exists(STORAGE_BASE_PATH):
        print("⚠️ Nenhuma pasta de índices encontrada.")
        return {}

    # Varre as pastas (index_engenharia, index_tecnologia, etc)
    for folder_name in os.listdir(STORAGE_BASE_PATH):
        if folder_name.startswith("index_"):
            area_name = folder_name.replace("index_", "") # Ex: 'engenharia'
            path = os.path.join(STORAGE_BASE_PATH, folder_name)
            
            try:
                # Carrega o FAISS
                vectorstore = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
                loaded_indexes[area_name] = vectorstore
                print(f"   ✅ Área carregada: {area_name.upper()}")
            except Exception as e:
                print(f"   ❌ Erro ao carregar {area_name}: {e}")

    return loaded_indexes

def get_rag_chain(area_selecionada="institucional"):
    """
    Cria a chain de conversação usando o índice da área específica.
    Se a área não existir, usa 'institucional' ou o primeiro disponível como fallback.
    """
    global loaded_indexes
    
    # 1. Seleciona o VectorStore correto
    vectorstore = loaded_indexes.get(area_selecionada)
    
    # Fallback: Se não achou a área (ou usuário não selecionou), tenta 'institucional' ou o primeiro que tiver
    if not vectorstore:
        if "institucional" in loaded_indexes:
            vectorstore = loaded_indexes["institucional"]
        elif loaded_indexes:
            vectorstore = list(loaded_indexes.values())[0]
        else:
            raise ValueError("Nenhum índice vetorial disponível. Rode o ingest_multiplo.py primeiro.")

    # 2. Configura o LLM (Usando LlamaCpp via LangChain ou sua classe customizada)
    # Ajuste os parâmetros conforme sua GPU/CPU
    llm = LlamaCpp(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_gpu_layers=-1, # -1 usa toda a GPU. Ajuste para 0 se for CPU.
        temperature=0.3,
        verbose=False
    )

    # 3. Define o Prompt (Com a regra dos quadrinhos $$ e blocos)
    qa_template = """<|im_start|>system
Você é o UCDB-IA, assistente acadêmico especialista na área de {area}.

REGRAS DE VISUAL E CONTEÚDO:
1. **FÓRMULAS MATEMÁTICAS:**
   - NUNCA escreva fórmulas importantes na mesma linha.
   - Use SEMPRE blocos destacados com `$$` no início e fim.
   - Exemplo:
     $$ V = R \cdot I $$
   - Use `$` apenas para citar variáveis pequenas no texto (ex: "onde $V$ é tensão").

2. **FORMATO:**
   - Use tabelas Markdown para comparações.
   - Use negrito para destacar conceitos chave.

3. Responda apenas com base no contexto abaixo. Se não souber, diga que o material desta área não cobre o assunto.<|im_end|>
<|im_start|>user
Contexto:
{context}

Pergunta:
{question}<|im_end|>
<|im_start|>assistant
"""
    # Injeta o nome da área no prompt para o modelo "entrar no personagem"
    qa_template = qa_template.format(area=area_selecionada.capitalize(), context="{context}", question="{question}")

    PROMPT = PromptTemplate(template=qa_template, input_variables=["context", "question"])

    # 4. Cria a Chain
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": PROMPT}
    )
    
    return chain