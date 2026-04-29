import os
import re
from pypdf import PdfReader, PdfWriter
from app.core.config import settings
from app.utils.performance import monitor_perf

def limpar_nome_arquivo(nome: str) -> str:
    """Remove caracteres inválidos para salvar o arquivo no Windows/Linux"""
    nome_limpo = re.sub(r'[\\/*?:"<>|]', "", nome)
    nome_limpo = nome_limpo.replace(" ", "_").replace("\n", "").replace("\r", "")
    return nome_limpo[:50] # Limita o tamanho do nome

def extrair_capitulos(reader: PdfReader):
    """Lê o sumário interativo (bookmarks) do PDF e retorna os nomes e páginas"""
    capitulos = []
    
    def percorrer_sumario(outline_list):
        for item in outline_list:
            if isinstance(item, list):
                percorrer_sumario(item) # Se for um subcapítulo, entra nele
            else:
                try:
                    titulo = item.title
                    pagina = reader.get_destination_page_number(item)
                    if pagina is not None:
                        capitulos.append({"titulo": titulo, "pagina": pagina})
                except Exception:
                    pass

    if reader.outline:
        percorrer_sumario(reader.outline)
        
    # Remove duplicatas e ordena pelas páginas
    capitulos_unicos = {}
    for cap in capitulos:
        if cap["pagina"] not in capitulos_unicos:
            capitulos_unicos[cap["pagina"]] = cap["titulo"]
            
    lista_ordenada = [{"titulo": titulo, "pagina": pag} for pag, titulo in sorted(capitulos_unicos.items())]
    return lista_ordenada

def quebrar_pdf_por_capitulos(pasta_alvo: str):
    """Procura PDFs e divide com base nos Capítulos/Leis"""
    for raiz, _, arquivos in os.walk(pasta_alvo):
        for arquivo in arquivos:
            if not arquivo.lower().endswith(".pdf") or "_parte_" in arquivo:
                continue
                
            caminho_completo = os.path.join(raiz, arquivo)
            print(f"\n📖 Analisando: {arquivo}...")
            
            try:
                reader = PdfReader(caminho_completo)
                total_paginas = len(reader.pages)
                
                capitulos = extrair_capitulos(reader)
                
                if not capitulos or len(capitulos) < 2:
                    print(f"⚠️ {arquivo} não tem um sumário digital válido. Ignorando...")
                    continue
                
                nome_base = os.path.splitext(arquivo)[0]
                print(f"✅ Encontrados {len(capitulos)} capítulos. Iniciando o fatiamento...")

                for i, cap_atual in enumerate(capitulos):
                    pagina_inicio = cap_atual["pagina"]
                    
                    # A página final é o início do próximo capítulo (ou o final do PDF)
                    if i + 1 < len(capitulos):
                        pagina_fim = capitulos[i + 1]["pagina"]
                    else:
                        pagina_fim = total_paginas
                        
                    # Ignora "capítulos" que tem 0 páginas (erros no PDF)
                    if pagina_inicio >= pagina_fim:
                        continue
                        
                    writer = PdfWriter()
                    for num_pagina in range(pagina_inicio, pagina_fim):
                        writer.add_page(reader.pages[num_pagina])
                        
                    titulo_seguro = limpar_nome_arquivo(cap_atual["titulo"])
                    nome_saida = f"{nome_base}_parte_{i+1:03d}_{titulo_seguro}.pdf"
                    caminho_saida = os.path.join(raiz, nome_saida)
                    
                    with open(caminho_saida, "wb") as f_saida:
                        writer.write(f_saida)
                        
                print(f"🎉 Pronto! O arquivo gigante foi fragmentado com sucesso.")
                os.remove(caminho_completo) # Opcional: Remove o arquivo gigante original
                
            except Exception as e:
                print(f"❌ Erro ao fatiar {arquivo}: {e}")

if __name__ == "__main__":
    print("Iniciando quebra inteligente de PDFs por Capítulos/Leis...")
    # Aponta para a sua pasta de PDFs
    quebrar_pdf_por_capitulos(settings.pdf_path)
    print("Processo finalizado!")

@monitor_perf("Quebra de PDF")
def quebrar_arquivo_unico(caminho_completo: str) -> list:
    """
    Recebe o caminho de um único PDF recém-salvo.
    Se tiver capítulos, divide, apaga o original e retorna a lista dos novos arquivos.
    Se não tiver, retorna uma lista com o próprio arquivo original.
    """
    arquivos_gerados = []
    arquivo_nome = os.path.basename(caminho_completo)
    raiz = os.path.dirname(caminho_completo)
    
    try:
        reader = PdfReader(caminho_completo)
        total_paginas = len(reader.pages)
        capitulos = extrair_capitulos(reader)
        
        # Se não tem sumário digital ou tem apenas 1 capítulo, usa particionamento por limite de páginas (fallback)
        if not capitulos or len(capitulos) < 2:
            print(f"⚠️ Sem sumário digital válido em {arquivo_nome}. Usando fatiamento por páginas (fallback)...")
            PAGINAS_POR_PARTE = 20
            if total_paginas <= PAGINAS_POR_PARTE:
                return [caminho_completo]
            
            nome_base = os.path.splitext(arquivo_nome)[0]
            for i in range(0, total_paginas, PAGINAS_POR_PARTE):
                pagina_inicio = i
                pagina_fim = min(i + PAGINAS_POR_PARTE, total_paginas)
                
                writer = PdfWriter()
                for num_pagina in range(pagina_inicio, pagina_fim):
                    writer.add_page(reader.pages[num_pagina])
                    
                nome_saida = f"{nome_base}_parte_{i//PAGINAS_POR_PARTE + 1:03d}.pdf"
                caminho_saida = os.path.join(raiz, nome_saida)
                
                with open(caminho_saida, "wb") as f_saida:
                    writer.write(f_saida)
                arquivos_gerados.append(caminho_saida)
            
            os.remove(caminho_completo)
            return arquivos_gerados
            
        nome_base = os.path.splitext(arquivo_nome)[0]
        
        for i, cap_atual in enumerate(capitulos):
            pagina_inicio = cap_atual["pagina"]
            pagina_fim = capitulos[i + 1]["pagina"] if i + 1 < len(capitulos) else total_paginas
                
            if pagina_inicio >= pagina_fim:
                continue
                
            writer = PdfWriter()
            for num_pagina in range(pagina_inicio, pagina_fim):
                writer.add_page(reader.pages[num_pagina])
                
            titulo_seguro = limpar_nome_arquivo(cap_atual["titulo"])
            nome_saida = f"{nome_base}_parte_{i+1:03d}_{titulo_seguro}.pdf"
            caminho_saida = os.path.join(raiz, nome_saida)
            
            with open(caminho_saida, "wb") as f_saida:
                writer.write(f_saida)
                
            arquivos_gerados.append(caminho_saida)
            
        # Remove o arquivo original gigante do disco para não ficar duplicado
        os.remove(caminho_completo) 
        return arquivos_gerados
        
    except Exception as e:
        print(f"❌ Erro ao tentar fatiar arquivo único '{arquivo_nome}': {e}")
        # Se der erro no fatiamento, devolve o arquivo original para o RAG indexar
        return [caminho_completo]