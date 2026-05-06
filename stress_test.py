import asyncio
import httpx
import time
import statistics
import json
import sys
import random

# Lista de perguntas variadas para simular uso real
TEST_QUESTIONS = [
    "Quais são as regras de matrícula para alunos?",
    "Como funciona o sistema de estágios da UCDB?",
    "Quais documentos são necessários para o ProUni?",
    "Como entro em contato com a coordenação de Engenharia?",
    "Existe algum manual do aluno disponível?",
    "Quais são as regras para bolsas de estudo?",
    "Como solicitar o passe do estudante?"
]

async def login(client, username, password):
    print(f"🔑 Tentando login como '{username}'...")
    try:
        response = await client.post("/login", json={
            "external_id": username,
            "password": password
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("✅ Login realizado com sucesso.")
            return token
        else:
            print(f"❌ Falha no login: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro na conexão para login: {e}")
        return None

async def simulate_chat(client, token, message, area="Geral"):
    headers = {"Authorization": f"Bearer {token}"}
    start_time = time.perf_counter()
    ttft = None  # Time To First Token
    total_duration = None
    
    try:
        async with client.stream("POST", "/chat", 
                               json={"message": message, "area": area},
                               headers=headers,
                               timeout=300.0) as response:
            
            if response.status_code != 200:
                return None, None, response.status_code

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[len("data: "):]
                    try:
                        event = json.loads(data_str)
                        
                        # Captura o primeiro chunk (TTFT)
                        if event.get("type") == "chunk" and ttft is None:
                            ttft = time.perf_counter() - start_time
                        
                        if event.get("type") == "complete":
                            break
                        if event.get("type") == "error":
                            return None, None, "chat_error"
                    except json.JSONDecodeError:
                        continue
        
        total_duration = time.perf_counter() - start_time
        return total_duration, ttft, 200
    except Exception as e:
        return None, None, str(type(e).__name__)

async def run_stress_test(concurrent_requests=10, username="admin", password="admin123"):
    base_url = "http://localhost:8000"
    print(f"\n" + "="*60)
    print(f"🚀 INICIANDO TESTE DE ESTRESSE FUNCIONAL")
    print(f"📍 Servidor: {base_url}")
    print(f"👥 Concorrência: {concurrent_requests} usuários simultâneos")
    print("="*60)
    
    async with httpx.AsyncClient(base_url=base_url, timeout=300.0) as client:
        # 1. Autenticação
        token = await login(client, username, password)
        if not token:
            print("🚫 Abortando teste: Falha na autenticação.")
            return

        # 2. Preparação das Tarefas
        print(f"⏳ Disparando requisições...")
        tasks = []
        for i in range(concurrent_requests):
            question = random.choice(TEST_QUESTIONS)
            tasks.append(simulate_chat(client, token, question))
            
        start_test = time.perf_counter()
        results = await asyncio.gather(*tasks)
        end_test = time.perf_counter() - start_test
        
        # 3. Processamento de Métricas
        durations = [r[0] for r in results if r[2] == 200]
        ttfts = [r[1] for r in results if r[2] == 200 and r[1] is not None]
        errors = [r[2] for r in results if r[2] != 200]
        
        # 4. Relatório
        print("\n" + "📊 RESULTADOS FINAIS")
        print("-" * 30)
        print(f"Duração Total do Teste: {end_test:.2f}s")
        print(f"Requisições Bem-sucedidas: {len(durations)}/{concurrent_requests}")
        print(f"Falhas Detectadas: {len(errors)}")
        
        if errors:
            from collections import Counter
            print(f"Detalhamento de Erros: {dict(Counter(errors))}")
            
        if durations:
            print("\n⏱️  LATÊNCIA (Tempo Total da Resposta)")
            print(f"  Média:  {statistics.mean(durations):.2f}s")
            print(f"  Mínima: {min(durations):.2f}s")
            print(f"  Máxima: {max(durations):.2f}s")
            if len(durations) > 1:
                print(f"  Desvio Padrão: {statistics.stdev(durations):.2f}s")

            if ttfts:
                print("\n⚡ TTFT (Time to First Token - Percepção de Velocidade)")
                print(f"  Média:  {statistics.mean(ttfts):.2f}s")
                print(f"  Mínima: {min(ttfts):.2f}s")
                print(f"  Máxima: {max(ttfts):.2f}s")
            
            print("\n📈 VAZÃO (Throughput)")
            rps = len(durations) / end_test
            print(f"  Taxa: {rps:.2f} requisições por segundo")
            
        print("="*60)

if __name__ == "__main__":
    count = 5 # Default mais conservador
    user = "admin"
    pw = "admin123"
    
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    if len(sys.argv) > 2:
        user = sys.argv[2]
    if len(sys.argv) > 3:
        pw = sys.argv[3]
    
    try:
        asyncio.run(run_stress_test(count, user, pw))
    except KeyboardInterrupt:
        print("\nTeste interrompido.")
    except Exception as e:
        print(f"\n❌ Erro crítico ao executar teste: {e}")
