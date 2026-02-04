import os
import shutil
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# --- CONFIGURAÇÕES ---
# Pastas que o sistema vai procurar dentro de 'pdfs/'
AREAS_DE_CONHECIMENTO = [
    "engenharia", 
    "tecnologia", 
    "institucional", 
    "saude", 
    "juridico"
]

CAMINHO_PDFS = "pdfs"
CAMINHO_STORAGE_BASE = "storage_indexes" # Pasta onde vamos guardar os índices prontos

# Modelo de Embedding (Usando HuggingFace localmente para garantir velocidade na ingestão)
# Você pode mudar para o mesmo modelo que usa no servidor se preferir
MODELO_EMBEDDING = "nomic-ai/nomic-embed-text-v1.5" 

def criar_indice_por_area():
    # Inicializa o modelo de embeddings
    print(f"📥 Carregando modelo de embedding: {MODELO_EMBEDDING}...")
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDING, model_kwargs={'trust_remote_code': True})

    for area in AREAS_DE_CONHECIMENTO:
        path_area = os.path.join(CAMINHO_PDFS, area)
        path_saida = os.path.join(CAMINHO_STORAGE_BASE, f"index_{area}")

        # 1. Verifica se a pasta existe e tem arquivos
        if not os.path.exists(path_area):
            print(f"⚠️  Pasta não encontrada, pulando: {area}")
            continue
        
        arquivos = [f for f in os.listdir(path_area) if f.endswith('.pdf')]
        if not arquivos:
            print(f"⚠️  Pasta vazia, pulando: {area}")
            continue

        print(f"\n🚀 PROCESSANDO ÁREA: {area.upper()} ({len(arquivos)} arquivos)")

        # 2. Carrega os PDFs
        loader = DirectoryLoader(path_area, glob="*.pdf", loader_cls=PyPDFLoader)
        documents = loader.load()
        print(f"   📄 {len(documents)} páginas carregadas.")

        # 3. Quebra em pedaços (Chunks)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        texts = text_splitter.split_documents(documents)
        print(f"   🧩 Quebrado em {len(texts)} trechos de texto.")

        # 4. Cria o Banco Vetorial (FAISS)
        print("   🧠 Gerando embeddings e indexando...")
        vectorstore = FAISS.from_documents(texts, embeddings)

        # 5. Salva no disco separado
        vectorstore.save_local(path_saida)
        print(f"   ✅ Índice salvo em: {path_saida}")

    print("\n🏁 Processo de ingestão múltipla finalizado!")

if __name__ == "__main__":
    # Cria pasta base de storage se não existir
    if not os.path.exists(CAMINHO_STORAGE_BASE):
        os.makedirs(CAMINHO_STORAGE_BASE)
    
    criar_indice_por_area()