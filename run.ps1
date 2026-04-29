# run.ps1 - Script para rodar o UCDB-IA com Docker

$DOCKER_COMPOSE_FILE = "docker-compose.yml"

function Check-Docker {
    if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker nao encontrado. Por favor, instale o Docker Desktop." -ForegroundColor Red
        exit
    }
}

function Check-Nvidia-Docker {
    $check = docker info | Select-String "Runtimes:.*nvidia"
    if (!$check) {
        Write-Host "NVIDIA Container Toolkit nao detectado no Docker." -ForegroundColor Yellow
        Write-Host "A IA pode rodar lentamente sem aceleracao por GPU." -ForegroundColor Yellow
    }
}

function Start-System {
    Write-Host "Iniciando UCDB-IA via Docker Compose..." -ForegroundColor Cyan
    
    $images = docker images -q ucdb-backend
    if (!$images) {
        Write-Host "Primeira execucao detectada. Instalando pacotes e bibliotecas..." -ForegroundColor Green
        docker-compose build
    }

    docker-compose up -d

    Write-Host "Sistema rodando!" -ForegroundColor Green
    Write-Host "Frontend: http://localhost:5173" -ForegroundColor Blue
    Write-Host "Backend:  http://localhost:8000" -ForegroundColor Blue
    Write-Host "LLM:      http://localhost:8080" -ForegroundColor Blue
    Write-Host "Embedding:http://localhost:8081" -ForegroundColor Blue
    Write-Host ""
    Write-Host "Para ver os logs, use: docker-compose logs -f" -ForegroundColor Gray
}

Check-Docker
Check-Nvidia-Docker
Start-System
