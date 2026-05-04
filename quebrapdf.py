import os
import re
import fitz  # PyMuPDF
from app.core.config import settings
from app.utils.performance import monitor_perf
from typing import List, Dict

def limpar_nome_arquivo(nome: str) -> str:
    """Remove caracteres inválidos para salvar o arquivo no Windows/Linux"""
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "", nome)
    nome_limpo = nome_limpo.replace(" ", "_").replace("\n", "").replace("\r", "")
    return nome_limpo[:50] # Limita o tamanho do nome

def extrair_capitulos(doc: fitz.Document) -> List[Dict]:
    """Lê o sumário (TOC) do PDF usando PyMuPDF e retorna os nomes e páginas."""
    toc = doc.get_toc()
    capitulos = []
    
    for level, title, page in toc:
        # PyMuPDF TOC page is 1-based, we'll keep it as 0-based for internal use
        capitulos.append({"titulo": title, "pagina": page - 1})
        
    # Remove duplicatas e ordena pelas páginas
    capitulos_unicos = {}
    for cap in capitulos:
        if cap["pagina"] not in capitulos_unicos:
            capitulos_unicos[cap["pagina"]] = cap["titulo"]
            
    lista_ordenada = [{"titulo": titulo, "pagina": pag} for pag, titulo in sorted(capitulos_unicos.items())]
    return lista_ordenada

@monitor_perf("Quebra de PDF")
def quebrar_pdf_por_capitulos(pasta_alvo: str):
    """Procura PDFs e divide com base nos Capítulos/Leis."""
    for raiz, _, arquivos in os.walk(pasta_alvo):
        for arquivo in arquivos:
            if not arquivo.lower().endswith(".pdf") or "_parte_" in arquivo:
                continue
                
            caminho_completo = os.path.join(raiz, arquivo)
            quebrar_arquivo_unico(caminho_completo)

def quebrar_arquivo_unico(caminho_completo: str) -> List[str]:
    """
    Recebe o caminho de um único PDF.
    Se tiver capítulos, divide, apaga o original e retorna a lista dos novos arquivos.
    """
    arquivos_gerados = []
    arquivo_nome = os.path.basename(caminho_completo)
    raiz = os.path.dirname(caminho_completo)
    
    try:
        doc = fitz.open(caminho_completo)
        total_paginas = len(doc)
        capitulos = extrair_capitulos(doc)
        
        # Se não tem sumário digital ou tem apenas 1 capítulo, usa particionamento por limite de páginas (fallback)
        if not capitulos or len(capitulos) < 2:
            PAGINAS_POR_PARTE = 20
            if total_paginas <= PAGINAS_POR_PARTE:
                doc.close()
                return [caminho_completo]
            
            nome_base = os.path.splitext(arquivo_nome)[0]
            for i in range(0, total_paginas, PAGINAS_POR_PARTE):
                pagina_inicio = i
                pagina_fim = min(i + PAGINAS_POR_PARTE, total_paginas)
                
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=pagina_inicio, to_page=pagina_fim - 1)
                
                nome_saida = f"{nome_base}_parte_{i//PAGINAS_POR_PARTE + 1:03d}.pdf"
                caminho_saida = os.path.join(raiz, nome_saida)
                
                new_doc.save(caminho_saida)
                new_doc.close()
                arquivos_gerados.append(caminho_saida)
            
            doc.close()
            os.remove(caminho_completo)
            return arquivos_gerados
            
        nome_base = os.path.splitext(arquivo_nome)[0]
        
        for i, cap_atual in enumerate(capitulos):
            pagina_inicio = cap_atual["pagina"]
            pagina_fim = capitulos[i + 1]["pagina"] if i + 1 < len(capitulos) else total_paginas
                
            if pagina_inicio >= pagina_fim or pagina_inicio < 0:
                continue
                
            new_doc = fitz.open()
            # Ajuste de segurança para não tentar inserir além do limite
            safe_to_page = min(pagina_fim - 1, total_paginas - 1)
            new_doc.insert_pdf(doc, from_page=pagina_inicio, to_page=safe_to_page)
            
            titulo_seguro = limpar_nome_arquivo(cap_atual["titulo"])
            nome_saida = f"{nome_base}_parte_{i+1:03d}_{titulo_seguro}.pdf"
            caminho_saida = os.path.join(raiz, nome_saida)
            
            new_doc.save(caminho_saida)
            new_doc.close()
            arquivos_gerados.append(caminho_saida)
            
        doc.close()
        os.remove(caminho_completo) 
        return arquivos_gerados
        
    except Exception as e:
        print(f"❌ Erro ao tentar fatiar arquivo único '{arquivo_nome}': {e}")
        return [caminho_completo]

if __name__ == "__main__":
    print("Iniciando quebra inteligente de PDFs com PyMuPDF...")
    quebrar_pdf_por_capitulos(settings.pdf_path)
    print("Processo finalizado!")
