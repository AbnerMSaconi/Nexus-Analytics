import asyncio
import httpx
import time
import statistics
from app.core.config import settings

async def simulate_chat(client, user_id, message, area="Geral"):
    start = time.perf_counter()
    try:
        # Nota: O endpoint de chat emite SSE. Vamos ler apenas para medir o tempo.
        async with client.stream("POST", "/chat", json={"message": message, "area": area}) as response:
            async for line in response.aiter_lines():
                if "complete" in line:
                    break
        duration = time.perf_counter() - start
        return duration
    except Exception as e:
        print(f"Erro na simulação: {e}")
        return None

async def run_stress_test(concurrent_requests=10):
    print(f"🚀 Iniciando Teste de Estresse: {concurrent_requests} requisições simultâneas...")
    
    # Supõe que o servidor está rodando na porta 8000
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(base_url=base_url, timeout=300.0) as client:
        # Primeiro, precisamos logar ou ter um token. 
        # Para simplificar o teste, assumimos que o servidor aceita requisições ou usamos um bypass de teste.
        # Aqui vamos apenas disparar as requisições de chat.
        
        tasks = []
        for i in range(concurrent_requests):
            tasks.append(simulate_chat(client, f"test_user_{i}", f"Pergunta de teste numero {i} para medir desempenho."))
            
        results = await asyncio.gather(*tasks)
        
        # Filtra falhas
        durations = [d for d in results if d is not None]
        
        if durations:
            print("\n" + "="*50)
            print("📊 RELATÓRIO DE DESEMPENHO (STRESS TEST)")
            print("="*50)
            print(f"Total de Requisições: {concurrent_requests}")
            print(f"Sucesso: {len(durations)}")
            print(f"Tempo Médio: {statistics.mean(durations):.2f}s")
            print(f"Tempo Mínimo: {min(durations):.2f}s")
            print(f"Tempo Máximo: {max(durations):.2f}s")
            if len(durations) > 1:
                print(f"Desvio Padrão: {statistics.stdev(durations):.2f}s")
            print("="*50)
            print("DICA: Verifique o console do Servidor Backend para ver os tempos detalhados")
            print("(Quebra de PDF, Ingestão, Reranking, Inferência, etc.)")
            print("="*50)

if __name__ == "__main__":
    import sys
    count = 10
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    
    try:
        asyncio.run(run_stress_test(count))
    except KeyboardInterrupt:
        print("\nTeste interrompido.")
