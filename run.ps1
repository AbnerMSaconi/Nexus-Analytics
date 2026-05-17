# run.ps1 - Inicia o Nexus e exibe logs em tempo real. Ctrl+C para parar.

if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker nao encontrado. Instale o Docker Desktop e tente novamente." -ForegroundColor Red
    exit 1
}

# Aviso de GPU (nao bloqueia)
$gpuOk = docker info 2>$null | Select-String "nvidia"
if (!$gpuOk) {
    Write-Host "[AVISO] NVIDIA runtime nao detectado — LLM pode rodar sem aceleracao por GPU." -ForegroundColor Yellow
}

# Build apenas se as imagens ainda nao existem
$backendImage  = docker images -q ucdb-ia-backend  2>$null
$frontendImage = docker images -q ucdb-ia-frontend 2>$null
if (!$backendImage -or !$frontendImage) {
    Write-Host "Construindo imagens pela primeira vez..." -ForegroundColor Cyan
    docker compose build
}

# Sobe os containers em background
Write-Host "Iniciando containers..." -ForegroundColor Cyan
docker compose up -d

Write-Host ""
Write-Host "  Nexus esta no ar:" -ForegroundColor Green
Write-Host "  Frontend  -> http://localhost:5173" -ForegroundColor Blue
Write-Host "  Backend   -> http://localhost:8000" -ForegroundColor Blue
Write-Host "  LLM       -> http://localhost:8080" -ForegroundColor Blue
Write-Host "  Embeddings-> http://localhost:8081" -ForegroundColor Blue
Write-Host ""
Write-Host "  Pressione Ctrl+C para encerrar os logs (os containers continuam rodando)." -ForegroundColor Gray
Write-Host "  Use 'docker compose down' para parar tudo." -ForegroundColor Gray
Write-Host ""

# Segue os logs de todos os containers ate Ctrl+C
try {
    docker compose logs --follow --tail=50
} finally {
    Write-Host ""
    Write-Host "Logs encerrados. Containers ainda estao rodando." -ForegroundColor Yellow
    Write-Host "Para parar tudo: docker compose down" -ForegroundColor Gray
}
