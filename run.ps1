# run.ps1 - Nexus Analytics Server Manager v1.0
# Gerenciador persistente do servidor -- menu interativo completo

Set-StrictMode -Off
$ErrorActionPreference = "SilentlyContinue"
$Script:ProjectRoot = $PSScriptRoot

# =============================================================================
# UTILITARIOS
# =============================================================================

function Write-Line { Write-Host ("  " + ("-" * 54)) -ForegroundColor DarkGray }

function Write-Header {
    param([string]$Section = "")
    Clear-Host
    Write-Host ""
    Write-Host "  +======================================================+" -ForegroundColor DarkBlue
    Write-Host "  |     NEXUS Analytics  --  Gerenciador do Servidor     |" -ForegroundColor White
    if ($Section) {
        $pad  = [math]::Max(0, 54 - $Section.Length)
        $left = [math]::Floor($pad / 2)
        $right = $pad - $left
        Write-Host ("  |" + (" " * $left) + $Section + (" " * $right) + "|") -ForegroundColor Cyan
    }
    Write-Host "  +======================================================+" -ForegroundColor DarkBlue
    Write-Host ""
}

function Get-ContainerInfo {
    param([string]$Name)
    $status   = docker inspect --format "{{.State.Status}}"      $Name 2>$null
    $health   = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{end}}" $Name 2>$null
    $restarts = docker inspect --format "{{.RestartCount}}"      $Name 2>$null
    return @{ Status = "$status"; Health = "$health"; Restarts = [int]"$restarts" }
}

function Write-ContainerLine {
    param([string]$Name, [string]$Label)
    $i   = Get-ContainerInfo -Name $Name
    $sym = switch ($i.Status) {
        "running" { "[OK]     " }
        "exited"  { "[PARADO] " }
        ""        { "[?]      " }
        default   { "[$($i.Status)] " }
    }
    $col = if ($i.Status -eq "running") { "Green" } elseif ($i.Status -eq "exited") { "Red" } else { "Yellow" }
    Write-Host "  $sym" -NoNewline -ForegroundColor $col
    Write-Host "$Label" -NoNewline -ForegroundColor Gray
    if ($i.Health -eq "healthy")       { Write-Host "  (healthy)"            -ForegroundColor DarkGreen }
    elseif ($i.Health -eq "unhealthy") { Write-Host "  (unhealthy)"          -ForegroundColor Red }
    elseif ($i.Restarts -gt 3)         { Write-Host "  ($($i.Restarts) reinicios!)" -ForegroundColor Yellow }
    else { Write-Host "" }
}

function Show-QuickStatus {
    Write-Host "  STATUS DOS CONTAINERS" -ForegroundColor DarkGray
    Write-ContainerLine -Name "ucdb-llm-server"        -Label "LLM Server"
    Write-ContainerLine -Name "ucdb-embedding-server"  -Label "Embeddings"
    Write-ContainerLine -Name "ucdb-backend"           -Label "Backend   "
    Write-ContainerLine -Name "ucdb-frontend"          -Label "Frontend  "
    Write-Host ""
}

function Read-EnvVar {
    param([string]$Key, [string]$Default)
    $envFile = Join-Path $Script:ProjectRoot ".env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^$Key=(.+)" } | Select-Object -First 1
        if ($line -match "^$Key=(.+)") { return $matches[1].Trim() }
    }
    return $Default
}

function Confirm-Action {
    param([string]$Message)
    $ans = Read-Host "  $Message (s/n)"
    return $ans -eq "s"
}

function Press-Enter { Read-Host "  [Enter para voltar]" | Out-Null }

function Write-EnvVar {
    param([string]$Key, [string]$Value)
    $envFile = Join-Path $Script:ProjectRoot ".env"

    if (-not (Test-Path $envFile)) {
        Set-Content -Path $envFile -Value "$Key=$Value" -Encoding utf8
        return
    }

    $lines = @(Get-Content $envFile)
    $found = $false
    $newLines = @()
    foreach ($line in $lines) {
        if ($line -match "^\s*$Key=") {
            $newLines += "$Key=$Value"
            $found = $true
        } else {
            $newLines += $line
        }
    }
    if (-not $found) { $newLines += "$Key=$Value" }
    Set-Content -Path $envFile -Value $newLines -Encoding utf8
}

function Get-ModelsDir {
    $dir = Read-EnvVar "MODELS_DIR" "D:/models"
    return $dir
}

function Get-AvailableModels {
    $dir = Get-ModelsDir
    if (-not (Test-Path $dir)) { return @() }
    return @(Get-ChildItem -Path $dir -Filter "*.gguf" -File -ErrorAction SilentlyContinue | Sort-Object Name)
}

# Executa SQL no SQLite do backend (sem CLI sqlite3 -- usa Python).
function Invoke-Sqlite {
    param(
        [Parameter(Mandatory = $true)][string]$Sql,
        [switch]$Quiet
    )
    $py = @"
import sqlite3, os
db = os.getenv('DATABASE_URL','sqlite:////app/ucdb_ia.db').replace('sqlite:///','').replace('sqlite:////','/')
if not db.startswith('/'): db = '/' + db
conn = sqlite3.connect(db)
cur = conn.cursor()
try:
    cur.execute('''$Sql''')
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    if cols:
        widths = [max(len(c), max((len(str(r[i])) for r in rows), default=0)) for i, c in enumerate(cols)]
        print(' | '.join(c.ljust(widths[i]) for i, c in enumerate(cols)))
        print('-+-'.join('-' * w for w in widths))
        for r in rows:
            print(' | '.join(str(r[i]).ljust(widths[i]) for i in range(len(cols))))
        print(f'\n({len(rows)} linha(s))')
    else:
        conn.commit()
        print(f'OK -- {cur.rowcount} linha(s) afetada(s).' if cur.rowcount >= 0 else 'OK')
except Exception as e:
    print(f'ERRO: {e}')
finally:
    conn.close()
"@
    if ($Quiet) {
        docker exec ucdb-backend python -c $py 2>&1 | Out-Null
    } else {
        docker exec ucdb-backend python -c $py
    }
}

function Show-ModelSelector {
    param(
        [string]$EnvKey   = "LLM_MODEL",
        [string]$Service  = "llm",
        [string]$Title    = "MODELO LLM (CHAT)"
    )
    Write-Header "SELECIONAR $Title"

    $models = Get-AvailableModels
    $dir    = Get-ModelsDir
    if ($models.Count -eq 0) {
        Write-Host "  Nenhum arquivo .gguf encontrado em: $dir" -ForegroundColor Red
        Write-Host "  Ajuste MODELS_DIR no .env ou coloque arquivos .gguf na pasta." -ForegroundColor DarkGray
        Press-Enter
        return
    }

    $current = Read-EnvVar $EnvKey "(nenhum)"
    Write-Host "  Diretorio: $dir" -ForegroundColor DarkGray
    Write-Host "  Atual    : $current" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Modelos disponiveis (* = atual):" -ForegroundColor Cyan
    Write-Host ""

    $i = 1
    foreach ($m in $models) {
        $size   = [math]::Round($m.Length / 1GB, 2)
        $marker = if ($m.Name -eq $current) { "*" } else { " " }
        Write-Host ("  {0} [{1,2}]  {2,-55} {3,6} GB" -f $marker, $i, $m.Name, $size)
        $i++
    }
    Write-Host ""
    Write-Host "  [0]  Cancelar" -ForegroundColor DarkGray
    Write-Host ""

    $choice = Read-Host "  Numero do modelo"
    if (-not $choice -or $choice -eq "0") { return }

    $idx = 0
    if (-not [int]::TryParse($choice, [ref]$idx)) {
        Write-Host "  Opcao invalida." -ForegroundColor Red; Start-Sleep 1; return
    }
    if ($idx -lt 1 -or $idx -gt $models.Count) {
        Write-Host "  Numero fora do intervalo." -ForegroundColor Red; Start-Sleep 1; return
    }

    $selected = $models[$idx - 1].Name
    if ($selected -eq $current) {
        Write-Host "  Esse ja e o modelo atual." -ForegroundColor Yellow; Start-Sleep 1; return
    }

    Write-Host ""
    Write-Host "  Selecionado: $selected" -ForegroundColor Green
    Write-EnvVar -Key $EnvKey -Value $selected
    Write-Host "  .env atualizado ($EnvKey)." -ForegroundColor Green
    Write-Host ""

    if (Confirm-Action "Recriar container '$Service' agora para aplicar?") {
        Write-Host "  Parando $Service..." -ForegroundColor Cyan
        docker compose stop $Service 2>&1 | Out-Null
        Write-Host "  Subindo $Service com o novo modelo..." -ForegroundColor Cyan
        docker compose up -d $Service 2>&1 | Out-Null
        Write-Host "  Pronto. O modelo pode levar alguns segundos para carregar na VRAM." -ForegroundColor Green
        Start-Sleep 1
    } else {
        Write-Host "  Alteracao salva no .env, mas o container nao foi recriado." -ForegroundColor Yellow
        Write-Host "  Use a opcao 'recarregar modelo' quando quiser aplicar." -ForegroundColor DarkGray
        Start-Sleep 2
    }
}

# =============================================================================
# SISTEMA -- INICIAR / PARAR
# =============================================================================

function Show-LLMSelector {
    while ($true) {
        Write-Header "SERVIDORES DE IA"
        Write-ContainerLine -Name "ucdb-llm-server"        -Label "LLM Server "
        Write-ContainerLine -Name "ucdb-embedding-server"  -Label "Embeddings "
        $curLlm = Read-EnvVar "LLM_MODEL"       "(default)"
        $curEmb = Read-EnvVar "EMBEDDING_MODEL" "(default)"
        Write-Host ""
        Write-Host "  Modelo LLM        : $curLlm" -ForegroundColor DarkGray
        Write-Host "  Modelo Embeddings : $curEmb" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  -- Trocar modelo (lista .gguf da pasta MODELS_DIR) --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [1]  Trocar modelo LLM"
        Write-Host "  [2]  Trocar modelo Embeddings"
        Write-Line
        Write-Host "  -- Restart rapido (mantem config) --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [3]  LLM Server (chat)"
        Write-Host "  [4]  Embeddings Server (busca)"
        Write-Host "  [5]  Ambos"
        Write-Line
        Write-Host "  -- Recarregar (stop + up, rele o yaml/.env) --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [6]  LLM Server"
        Write-Host "  [7]  Embeddings Server"
        Write-Host "  [8]  Ambos"
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        switch ($choice) {
            "1" { Show-ModelSelector -EnvKey "LLM_MODEL"       -Service "llm"        -Title "MODELO LLM (CHAT)" }
            "2" { Show-ModelSelector -EnvKey "EMBEDDING_MODEL" -Service "embeddings" -Title "MODELO EMBEDDINGS (BUSCA)" }
            "3" {
                Write-Host "  Reiniciando LLM Server..." -ForegroundColor Cyan
                docker compose restart llm
                Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1
            }
            "4" {
                Write-Host "  Reiniciando Embeddings Server..." -ForegroundColor Cyan
                docker compose restart embeddings
                Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1
            }
            "5" {
                Write-Host "  Reiniciando LLM + Embeddings..." -ForegroundColor Cyan
                docker compose restart llm embeddings
                Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1
            }
            "6" {
                Write-Host "  Recarregando LLM (stop + up)..." -ForegroundColor Cyan
                docker compose stop llm   2>&1 | Out-Null
                docker compose up -d llm  2>&1 | Out-Null
                Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1
            }
            "7" {
                Write-Host "  Recarregando Embeddings (stop + up)..." -ForegroundColor Cyan
                docker compose stop embeddings   2>&1 | Out-Null
                docker compose up -d embeddings  2>&1 | Out-Null
                Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1
            }
            "8" {
                Write-Host "  Recarregando LLM + Embeddings (stop + up)..." -ForegroundColor Cyan
                docker compose stop llm embeddings   2>&1 | Out-Null
                docker compose up -d llm embeddings  2>&1 | Out-Null
                Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1
            }
            "0" { return }
            default { }
        }
    }
}

function Show-RebuildSelector {
    Write-Header "REBUILD SELETIVO"
    Write-Host "  Selecione o que deseja rebuildar:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [1]  Backend apenas"
    Write-Host "  [2]  Frontend apenas"
    Write-Host "  [3]  Backend + Frontend"
    Write-Host "  [4]  Backend + Frontend  (com --pull das imagens base)"
    Write-Host ""
    Write-Host "  [0]  Cancelar" -ForegroundColor DarkGray
    Write-Host ""
    $choice = Read-Host "  Opcao"

    switch ($choice) {
        "1" { return @{ Backend = $true;  Frontend = $false; Pull = $false } }
        "2" { return @{ Backend = $false; Frontend = $true;  Pull = $false } }
        "3" { return @{ Backend = $true;  Frontend = $true;  Pull = $false } }
        "4" { return @{ Backend = $true;  Frontend = $true;  Pull = $true  } }
        default { return $null }
    }
}

function Test-EnvFile {
    $envFile = Join-Path $Script:ProjectRoot ".env"
    if (Test-Path $envFile) { return $true }

    Write-Host ""
    Write-Host "  [!] Arquivo .env nao encontrado." -ForegroundColor Yellow
    $example = Join-Path $Script:ProjectRoot ".env.example"
    if (Test-Path $example) {
        if (Confirm-Action "Copiar .env.example para .env agora?") {
            Copy-Item $example $envFile -Force
            Write-Host "  .env criado. Edite-o se necessario antes de iniciar." -ForegroundColor Green
            return $true
        }
    } else {
        Write-Host "  .env.example tambem nao encontrado. Crie um .env antes de iniciar." -ForegroundColor Red
    }
    return $false
}

function Test-ModelFiles {
    $modelsDir = Read-EnvVar "MODELS_DIR" ""
    $llm       = Read-EnvVar "LLM_MODEL" ""
    $emb       = Read-EnvVar "EMBEDDING_MODEL" ""
    $issues    = @()

    if (-not $modelsDir) { $issues += "MODELS_DIR nao definido no .env" }
    elseif (-not (Test-Path $modelsDir)) { $issues += "MODELS_DIR nao existe: $modelsDir" }
    else {
        if ($llm -and -not (Test-Path (Join-Path $modelsDir $llm))) { $issues += "LLM_MODEL nao encontrado: $modelsDir\$llm" }
        if ($emb -and -not (Test-Path (Join-Path $modelsDir $emb))) { $issues += "EMBEDDING_MODEL nao encontrado: $modelsDir\$emb" }
    }

    if ($issues.Count -gt 0) {
        Write-Host ""
        Write-Host "  [!] Problemas com os modelos .gguf:" -ForegroundColor Yellow
        foreach ($i in $issues) { Write-Host "       - $i" -ForegroundColor Yellow }
        Write-Host "       LLM/Embeddings vao falhar ate isso ser corrigido." -ForegroundColor DarkGray
        Write-Host ""
    }
}

function Invoke-ComposeUp {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][string]$Container,
        [Parameter(Mandatory = $true)][string]$Step,
        [switch]$NoDeps
    )
    Write-Host "  $Step $Service..." -ForegroundColor Cyan
    if ($NoDeps) {
        docker compose up -d --no-deps $Service
    } else {
        docker compose up -d $Service
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FALHA] docker compose retornou codigo $LASTEXITCODE para '$Service'." -ForegroundColor Red
        Write-Host "  Veja os logs com: docker compose logs $Service" -ForegroundColor DarkGray
        return $false
    }
    Start-Sleep -Milliseconds 800
    $status = docker inspect --format "{{.State.Status}}" $Container 2>$null
    if ($status -ne "running") {
        Write-Host "  [FALHA] '$Container' nao esta rodando (status: $status)." -ForegroundColor Red
        Write-Host "  ultimas 20 linhas do log:" -ForegroundColor DarkGray
        docker logs --tail 20 $Container 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        return $false
    }
    Write-Host "  OK -- $Container" -ForegroundColor Green
    return $true
}

function Start-Nexus {
    param([hashtable]$Rebuild = $null)
    Write-Host ""

    if (-not (Test-EnvFile)) { Press-Enter; return }
    Test-ModelFiles

    $rebuildBackend  = ($Rebuild -ne $null) -and $Rebuild.Backend
    $rebuildFrontend = ($Rebuild -ne $null) -and $Rebuild.Frontend
    $pullBase        = ($Rebuild -ne $null) -and $Rebuild.Pull

    $llmUp = docker ps --filter "name=ucdb-llm-server" --filter "status=running" -q
    if ($llmUp) {
        Write-Host "  [1/4] LLM Server ja rodando." -ForegroundColor Green
    } else {
        [void](Invoke-ComposeUp -Service "llm" -Container "ucdb-llm-server" -Step "[1/4]")
    }

    $embUp = docker ps --filter "name=ucdb-embedding-server" --filter "status=running" -q
    if ($embUp) {
        Write-Host "  [2/4] Embeddings ja rodando." -ForegroundColor Green
    } else {
        [void](Invoke-ComposeUp -Service "embeddings" -Container "ucdb-embedding-server" -Step "[2/4]")
    }

    if ($rebuildBackend) {
        $tag = if ($pullBase) { "Rebuild --pull + Backend" } else { "Rebuild + Backend" }
        Write-Host "  [3/4] $tag..." -ForegroundColor Cyan
        if ($pullBase) { docker compose build --pull backend } else { docker compose build backend }
        if ($LASTEXITCODE -ne 0) { Write-Host "  [FALHA] build do backend falhou." -ForegroundColor Red; Press-Enter; return }
    }
    [void](Invoke-ComposeUp -Service "backend" -Container "ucdb-backend" -Step "[3/4]" -NoDeps)

    $frontUp = docker ps --filter "name=ucdb-frontend" --filter "status=running" -q
    if ($frontUp -and -not $rebuildFrontend) {
        Write-Host "  [4/4] Frontend ja rodando." -ForegroundColor Green
    } else {
        if ($rebuildFrontend) {
            $tag = if ($pullBase) { "Rebuild --pull + Frontend" } else { "Rebuild + Frontend" }
            Write-Host "  [4/4] $tag..." -ForegroundColor Cyan
            if ($pullBase) { docker compose build --pull frontend } else { docker compose build frontend }
            if ($LASTEXITCODE -ne 0) { Write-Host "  [FALHA] build do frontend falhou." -ForegroundColor Red; Press-Enter; return }
        }
        [void](Invoke-ComposeUp -Service "frontend" -Container "ucdb-frontend" -Step "[4/4]" -NoDeps)
    }

    Write-Host ""
    Write-Host "  Sistema iniciado." -ForegroundColor Green
    Write-Host "  Frontend  -> http://localhost:5173" -ForegroundColor Blue
    Write-Host "  API       -> http://localhost:8000" -ForegroundColor Blue
    Write-Host ""
    Press-Enter
}

function Stop-Nexus {
    param([switch]$WithVolumes)
    Write-Host ""
    if ($WithVolumes) {
        Write-Host "  Parando e removendo volumes..." -ForegroundColor Yellow
        docker compose down -v
    } else {
        Write-Host "  Parando containers..." -ForegroundColor Yellow
        docker compose down
    }
    Write-Host "  Sistema parado." -ForegroundColor Green
    Write-Host ""
    Start-Sleep -Seconds 1
}

# =============================================================================
# MONITORAMENTO EM TEMPO REAL
# =============================================================================

function Show-Monitoring {
    Write-Host "  Iniciando monitoramento... Pressione [Q] para sair." -ForegroundColor DarkGray
    Start-Sleep -Seconds 1

    while ($true) {
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq "Q") { break }
        }

        $ts = Get-Date -Format "HH:mm:ss  dd/MM/yyyy"
        Clear-Host
        Write-Host ""
        Write-Host "  +======================================================+" -ForegroundColor DarkBlue
        Write-Host "  |       NEXUS Analytics -- Monitoramento Tempo Real    |" -ForegroundColor White
        Write-Host "  |  $ts                      [Q] sair  |" -ForegroundColor DarkGray
        Write-Host "  +======================================================+" -ForegroundColor DarkBlue
        Write-Host ""

        Write-Host "  CONTAINERS" -ForegroundColor Cyan
        Write-ContainerLine -Name "ucdb-llm-server"        -Label "LLM Server "
        Write-ContainerLine -Name "ucdb-embedding-server"  -Label "Embeddings "
        Write-ContainerLine -Name "ucdb-backend"           -Label "Backend    "
        Write-ContainerLine -Name "ucdb-frontend"          -Label "Frontend   "
        Write-Host ""

        Write-Host "  RECURSOS DOS CONTAINERS" -ForegroundColor Cyan
        $stats = docker stats --no-stream --format "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}" 2>$null
        if ($stats) {
            Write-Host ("  {0,-28} {1,8} {2,22} {3,22}" -f "CONTAINER","CPU","MEMORIA","REDE") -ForegroundColor DarkGray
            $stats | ForEach-Object {
                $p = $_ -split "\|"
                if ($p.Count -ge 4) {
                    Write-Host ("  {0,-28} {1,8} {2,22} {3,22}" -f $p[0],$p[1],$p[2],$p[3]) -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "  Nenhum container em execucao." -ForegroundColor DarkGray
        }
        Write-Host ""

        Write-Host "  GPU" -ForegroundColor Cyan
        $gpuRaw = nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader,nounits 2>$null
        if ($gpuRaw) {
            $gpuRaw | ForEach-Object {
                $g = $_ -split ","
                if ($g.Count -ge 5) {
                    $temp  = [int]$g[1].Trim()
                    $util  = [int]$g[2].Trim()
                    $mUsed = [math]::Round([int]$g[3].Trim() / 1024, 1)
                    $mTot  = [math]::Round([int]$g[4].Trim() / 1024, 1)
                    $pwr   = if ($g.Count -ge 6) { "$($g[5].Trim())W" } else { "N/A" }
                    $tcol  = if ($temp -gt 85) { "Red" } elseif ($temp -gt 70) { "Yellow" } else { "Green" }
                    Write-Host "  $($g[0].Trim())" -ForegroundColor White
                    Write-Host "    Temp: " -NoNewline -ForegroundColor DarkGray
                    Write-Host "${temp}C  " -NoNewline -ForegroundColor $tcol
                    Write-Host "GPU: ${util}%  VRAM: ${mUsed}/${mTot} GB  Power: $pwr" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "  nvidia-smi indisponivel ou sem GPU detectada." -ForegroundColor DarkGray
        }
        Write-Host ""

        Write-Host "  HOST" -ForegroundColor Cyan
        try {
            $cpuLoad = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
            $os      = Get-CimInstance Win32_OperatingSystem
            $ramUsed = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 1)
            $ramTot  = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
            $disk    = Get-PSDrive C
            $dUsed   = [math]::Round($disk.Used / 1GB, 1)
            $dFree   = [math]::Round($disk.Free / 1GB, 1)
            Write-Host "  CPU: ${cpuLoad}%   RAM: ${ramUsed}/${ramTot} GB   Disco C: ${dUsed} GB usado / ${dFree} GB livre" -ForegroundColor Gray
        } catch {
            Write-Host "  Nao foi possivel obter metricas do host." -ForegroundColor DarkGray
        }
        Write-Host ""

        Start-Sleep -Seconds 5
    }
}

# =============================================================================
# HEALTH CHECK
# =============================================================================

function Invoke-HealthCheck {
    Write-Host ""
    Write-Host "  Verificando saude do sistema..." -ForegroundColor Cyan
    Write-Host ""
    $issues = 0

    Write-Host "  CONTAINERS" -ForegroundColor White
    $containers = @(
        @{ Name = "ucdb-llm-server";        Label = "LLM Server"     },
        @{ Name = "ucdb-embedding-server";  Label = "Embeddings"     },
        @{ Name = "ucdb-backend";           Label = "Backend"        },
        @{ Name = "ucdb-frontend";          Label = "Frontend"       }
    )
    foreach ($c in $containers) {
        $i = Get-ContainerInfo -Name $c.Name
        if ($i.Status -eq "running") {
            $warn = if ($i.Restarts -gt 3) { " [!] $($i.Restarts) reinicializacoes!" } else { "" }
            $col  = if ($i.Restarts -gt 3) { "Yellow" } else { "Green" }
            Write-Host "  [OK]   $($c.Label)$warn" -ForegroundColor $col
            if ($i.Restarts -gt 3) { $issues++ }
        } else {
            Write-Host "  [FAIL] $($c.Label)  (status: $($i.Status))" -ForegroundColor Red
            $issues++
        }
    }
    Write-Host ""

    Write-Host "  ENDPOINTS HTTP" -ForegroundColor White
    $endpoints = @(
        @{ Url = "http://localhost:8000/health"; Label = "Backend    /health" },
        @{ Url = "http://localhost:8080/health"; Label = "LLM        /health" },
        @{ Url = "http://localhost:8081/health"; Label = "Embeddings /health" }
    )
    foreach ($ep in $endpoints) {
        try {
            $r = Invoke-WebRequest -Uri $ep.Url -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            Write-Host "  [OK]   $($ep.Label)  $($r.StatusCode)" -ForegroundColor Green
        } catch {
            Write-Host "  [FAIL] $($ep.Label)  sem resposta" -ForegroundColor Red
            $issues++
        }
    }
    Write-Host ""

    Write-Host "  BANCO DE DADOS (SQLite)" -ForegroundColor White
    $dbFile = Join-Path $Script:ProjectRoot "backend\ucdb_ia.db"
    if (Test-Path $dbFile) {
        $sizeMB = [math]::Round((Get-Item $dbFile).Length / 1MB, 2)
        Write-Host "  [OK]   ucdb_ia.db  (${sizeMB} MB)" -ForegroundColor Green
    } else {
        Write-Host "  [!]    ucdb_ia.db nao encontrado em backend/" -ForegroundColor Yellow
        Write-Host "         Inicialize as tabelas pelo menu Banco de Dados." -ForegroundColor DarkGray
    }
    Write-Host ""

    Write-Host "  DISCO" -ForegroundColor White
    $disk  = Get-PSDrive C
    $free  = [math]::Round($disk.Free / 1GB, 1)
    $used  = [math]::Round($disk.Used / 1GB, 1)
    $total = $free + $used
    $pct   = [math]::Round($used / $total * 100, 0)
    $dcol  = if ($free -lt 5) { "Red" } elseif ($free -lt 20) { "Yellow" } else { "Green" }
    Write-Host "  Disco C: ${used}/${total} GB usados (${pct}%)  --  ${free} GB livres" -ForegroundColor $dcol
    if ($free -lt 5) { $issues++; Write-Host "  [!] Espaco critico em disco!" -ForegroundColor Red }
    Write-Host ""

    Write-Host "  GPU" -ForegroundColor White
    $gpuRaw = nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu --format=csv,noheader,nounits 2>$null
    if ($gpuRaw) {
        $g    = $gpuRaw -split ","
        $temp = [int]$g[1].Trim()
        $util = [int]$g[2].Trim()
        $tcol = if ($temp -gt 85) { "Red" } elseif ($temp -gt 70) { "Yellow" } else { "Green" }
        Write-Host "  $($g[0].Trim())  Temp: ${temp}C  Util: ${util}%" -ForegroundColor $tcol
        if ($temp -gt 85) { $issues++ }
    } else {
        Write-Host "  nvidia-smi indisponivel -- GPU nao verificada." -ForegroundColor DarkGray
    }
    Write-Host ""

    Write-Host "  VOLUMES DOCKER" -ForegroundColor White
    docker system df 2>$null | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    Write-Host ""

    if ($issues -eq 0) {
        Write-Host "  Tudo saudavel. Nenhum problema detectado." -ForegroundColor Green
    } else {
        Write-Host "  $issues problema(s) encontrado(s). Revise os itens acima." -ForegroundColor Red
    }
    Write-Host ""
    Press-Enter
}

# =============================================================================
# LOGS
# =============================================================================

function Show-LogsMenu {
    while ($true) {
        Write-Header "LOGS"
        Write-Host "  -- Tempo real (Ctrl+C para parar o streaming) --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [1]  Backend         (tempo real)"
        Write-Host "  [2]  Frontend        (tempo real)"
        Write-Host "  [3]  LLM Server      (tempo real)"
        Write-Host "  [4]  Embeddings      (tempo real)"
        Write-Host "  [5]  Todos           (tempo real)"
        Write-Line
        Write-Host "  -- Historico --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [6]  Backend         (ultimas 300 linhas)"
        Write-Host "  [7]  LLM Server      (ultimas 300 linhas)"
        Write-Host "  [8]  Todos           (ultimas 300 linhas)"
        Write-Line
        Write-Host "  -- Filtros --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [9]  Backend         - apenas erros/exceptions"
        Write-Host "  [10] Todos           - apenas erros/exceptions"
        Write-Host "  [11] Backend         - salvar em arquivo (.log)"
        Write-Host "  [12] Todos           - salvar em arquivo (.log)"
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        switch ($choice) {
            "1"  { docker compose logs -f backend }
            "2"  { docker compose logs -f frontend }
            "3"  { docker compose logs -f llm }
            "4"  { docker compose logs -f embeddings }
            "5"  { docker compose logs -f }
            "6"  { docker compose logs --tail=300 backend; Press-Enter }
            "7"  { docker compose logs --tail=300 llm; Press-Enter }
            "8"  { docker compose logs --tail=300; Press-Enter }
            "9" {
                docker compose logs --tail=1000 backend 2>&1 |
                    Select-String "error|Error|ERROR|exception|Exception|CRITICAL|traceback|Traceback|Warning" |
                    Select-Object -Last 80
                Press-Enter
            }
            "10" {
                docker compose logs --tail=1000 2>&1 |
                    Select-String "error|Error|ERROR|exception|Exception|CRITICAL|traceback|Traceback" |
                    Select-Object -Last 80
                Press-Enter
            }
            "11" {
                $file = "log_backend_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
                docker compose logs --tail=5000 backend | Out-File -Encoding utf8 $file
                Write-Host "  Salvo em: $file" -ForegroundColor Green; Press-Enter
            }
            "12" {
                $file = "log_all_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
                docker compose logs --tail=5000 | Out-File -Encoding utf8 $file
                Write-Host "  Salvo em: $file" -ForegroundColor Green; Press-Enter
            }
            "0"  { return }
        }
    }
}

# =============================================================================
# GERENCIAR CONTAINERS
# =============================================================================

function Show-ContainerMenu {
    while ($true) {
        Write-Header "GERENCIAR CONTAINERS"
        Show-QuickStatus
        Write-Host "  -- Reiniciar --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [1]  Reiniciar Backend"
        Write-Host "  [2]  Reiniciar Frontend"
        Write-Host "  [3]  Reiniciar LLM Server"
        Write-Host "  [4]  Reiniciar Embeddings"
        Write-Host "  [5]  Reiniciar TODOS"
        Write-Line
        Write-Host "  -- Rebuild --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [6]  Rebuild + Reiniciar Backend"
        Write-Host "  [7]  Rebuild + Reiniciar Frontend"
        Write-Host "  [8]  Rebuild completo (Backend + Frontend)"
        Write-Host "  [9]  Rebuild com pull das imagens base"
        Write-Line
        Write-Host "  -- Parar / Iniciar / Inspecionar --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [10] Parar container"
        Write-Host "  [11] Iniciar container"
        Write-Host "  [12] Remover container (force)"
        Write-Host "  [13] Inspecionar container (docker inspect)"
        Write-Host "  [14] Abrir shell no container"
        Write-Host "  [15] docker ps -a"
        Write-Host "  [16] Ver imagens Docker"
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        $done = { Write-Host "  Pronto." -ForegroundColor Green; Start-Sleep 1 }

        switch ($choice) {
            "1"  { docker compose restart backend;    & $done }
            "2"  { docker compose restart frontend;   & $done }
            "3"  { docker compose restart llm;        & $done }
            "4"  { docker compose restart embeddings; & $done }
            "5"  { docker compose restart;            & $done }
            "6"  { docker compose build backend; docker compose up -d --no-deps backend; & $done }
            "7"  { docker compose build frontend; docker compose up -d --no-deps frontend; & $done }
            "8"  { docker compose build backend frontend; docker compose up -d --no-deps backend frontend; & $done }
            "9"  { docker compose build --pull backend frontend; docker compose up -d --no-deps backend frontend; & $done }
            "10" {
                $c = Read-Host "  Container (backend | frontend | llm | embeddings)"
                docker compose stop $c
                Write-Host "  '$c' parado." -ForegroundColor Yellow; Start-Sleep 1
            }
            "11" {
                $c = Read-Host "  Container (backend | frontend | llm | embeddings)"
                docker compose start $c; & $done
            }
            "12" {
                $c = Read-Host "  Nome do container (ex: ucdb-backend)"
                if (Confirm-Action "Remover container '$c'?") { docker rm -f $c; & $done }
            }
            "13" {
                $c = Read-Host "  Nome do container (ex: ucdb-backend)"
                docker inspect $c; Press-Enter
            }
            "14" {
                $c  = Read-Host "  Container (ex: ucdb-backend)"
                $sh = Read-Host "  Shell [Enter = sh]"
                if (!$sh) { $sh = "sh" }
                docker exec -it $c $sh
            }
            "15" { docker ps -a; Press-Enter }
            "16" { docker images; Press-Enter }
            "0"  { return }
        }
    }
}

# =============================================================================
# CONSULTAS DAC (escolas + dados escolares)
# =============================================================================

# Exporta o resultado de uma query para CSV no host (via docker exec + cp).
function Export-DacCsv {
    param(
        [Parameter(Mandatory = $true)][string]$Sql,
        [Parameter(Mandatory = $true)][string]$BaseName
    )
    $ts   = Get-Date -Format "yyyyMMdd_HHmmss"
    $dest = Join-Path $Script:ProjectRoot "${BaseName}_${ts}.csv"
    $py = @"
import sqlite3, csv
conn = sqlite3.connect('/app/ucdb_ia.db')
cur = conn.cursor()
cur.execute('''$Sql''')
cols = [d[0] for d in cur.description]
with open('/app/_export_tmp.csv','w',newline='',encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(cols)
    n = 0
    for row in cur:
        w.writerow(row); n += 1
print(f'{n} linhas')
conn.close()
"@
    $count = docker exec ucdb-backend python -c $py
    docker cp "ucdb-backend:/app/_export_tmp.csv" $dest 2>&1 | Out-Null
    docker exec ucdb-backend rm -f /app/_export_tmp.csv 2>&1 | Out-Null
    if (Test-Path $dest) {
        Write-Host "  CSV salvo: $dest  ($count)" -ForegroundColor Green
    } else {
        Write-Host "  Falha ao exportar." -ForegroundColor Red
    }
}

function Show-DacQueriesMenu {
    while ($true) {
        Write-Header "CONSULTAS DAC (escolas + dados escolares)"
        Write-Host "  Tabelas: dac_escolas (id, nome, municipio)" -ForegroundColor DarkGray
        Write-Host "           dac_dados_escolares (escola_id, ano, total_matriculas, ..." -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  -- dac_escolas --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [1]  Listar TODAS as escolas (nome | municipio)"
        Write-Host "  [2]  Buscar escola por nome (LIKE)"
        Write-Host "  [3]  Listar escolas de um municipio"
        Write-Host "  [4]  Contagem de escolas por municipio"
        Write-Line
        Write-Host "  -- dac_dados_escolares (com JOIN em escolas) --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [5]  Dados de uma escola (todos os anos)"
        Write-Host "  [6]  Todos os registros de um ano"
        Write-Host "  [7]  Top 20 escolas por matriculas em um ano"
        Write-Host "  [8]  Resumo por municipio em um ano"
        Write-Host "  [9]  Resumo agregado por ano (matriculas/aprov/reprov/abandono)"
        Write-Host "  [10] JOIN completo (escola + dados, primeiras 50 linhas)"
        Write-Line
        Write-Host "  -- Exportacao para CSV --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [11] Exportar dac_escolas completa para CSV"
        Write-Host "  [12] Exportar dac_dados_escolares completa para CSV"
        Write-Host "  [13] Exportar JOIN completo (escola+municipio+dados) para CSV"
        Write-Host "  [14] Exportar JOIN filtrado por ano para CSV"
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        switch ($choice) {
            "1" {
                Invoke-Sqlite -Sql "SELECT nome, municipio FROM dac_escolas ORDER BY municipio, nome"
                Press-Enter
            }
            "2" {
                $q = Read-Host "  Trecho do nome (sera buscado com LIKE %...%)"
                if ($q) {
                    $qEsc = $q.Replace("'", "''")
                    Invoke-Sqlite -Sql "SELECT nome, municipio FROM dac_escolas WHERE nome LIKE '%$qEsc%' ORDER BY nome"
                }
                Press-Enter
            }
            "3" {
                $m = Read-Host "  Nome do municipio"
                if ($m) {
                    $mEsc = $m.Replace("'", "''")
                    Invoke-Sqlite -Sql "SELECT nome FROM dac_escolas WHERE municipio LIKE '%$mEsc%' ORDER BY nome"
                }
                Press-Enter
            }
            "4" {
                Invoke-Sqlite -Sql "SELECT municipio, COUNT(*) AS escolas FROM dac_escolas GROUP BY municipio ORDER BY escolas DESC"
                Press-Enter
            }
            "5" {
                $q = Read-Host "  Trecho do nome da escola"
                if ($q) {
                    $qEsc = $q.Replace("'", "''")
                    Invoke-Sqlite -Sql "SELECT e.nome, e.municipio, d.ano, d.total_matriculas, d.aprovados, d.reprovados, d.abandono, d.transferidos, d.cancelados FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id WHERE e.nome LIKE '%$qEsc%' ORDER BY e.nome, d.ano"
                }
                Press-Enter
            }
            "6" {
                $a = Read-Host "  Ano (ex: 2023)"
                if ($a -match '^\d+$') {
                    Invoke-Sqlite -Sql "SELECT e.municipio, e.nome, d.total_matriculas, d.aprovados, d.reprovados, d.abandono FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id WHERE d.ano = $a ORDER BY e.municipio, e.nome"
                } else { Write-Host "  Ano invalido." -ForegroundColor Red }
                Press-Enter
            }
            "7" {
                $a = Read-Host "  Ano (ex: 2023)"
                if ($a -match '^\d+$') {
                    Invoke-Sqlite -Sql "SELECT e.nome, e.municipio, d.total_matriculas FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id WHERE d.ano = $a ORDER BY d.total_matriculas DESC LIMIT 20"
                } else { Write-Host "  Ano invalido." -ForegroundColor Red }
                Press-Enter
            }
            "8" {
                $a = Read-Host "  Ano (ex: 2023)"
                if ($a -match '^\d+$') {
                    Invoke-Sqlite -Sql "SELECT e.municipio, COUNT(DISTINCT e.id) AS escolas, SUM(d.total_matriculas) AS matriculas, SUM(d.aprovados) AS aprov, SUM(d.reprovados) AS reprov, SUM(d.abandono) AS abandono FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id WHERE d.ano = $a GROUP BY e.municipio ORDER BY matriculas DESC"
                } else { Write-Host "  Ano invalido." -ForegroundColor Red }
                Press-Enter
            }
            "9" {
                Invoke-Sqlite -Sql "SELECT ano, COUNT(*) AS linhas, SUM(total_matriculas) AS matriculas, SUM(aprovados) AS aprov, SUM(reprovados) AS reprov, SUM(abandono) AS abandono FROM dac_dados_escolares GROUP BY ano ORDER BY ano"
                Press-Enter
            }
            "10" {
                Invoke-Sqlite -Sql "SELECT e.nome, e.municipio, d.ano, d.total_matriculas, d.aprovados, d.reprovados, d.abandono FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id ORDER BY e.municipio, e.nome, d.ano LIMIT 50"
                Press-Enter
            }
            "11" {
                Export-DacCsv -BaseName "dac_escolas" -Sql "SELECT id, nome, municipio FROM dac_escolas ORDER BY municipio, nome"
                Press-Enter
            }
            "12" {
                Export-DacCsv -BaseName "dac_dados_escolares" -Sql "SELECT id, escola_id, ano, total_matriculas, matricula_inicial, matricula_apos_censo, transferidos, cancelados, falecido, abandono, aprovados, reprovados, cursando, outras_situacoes FROM dac_dados_escolares ORDER BY ano, escola_id"
                Press-Enter
            }
            "13" {
                Export-DacCsv -BaseName "dac_join_completo" -Sql "SELECT e.nome AS escola, e.municipio, d.ano, d.total_matriculas, d.matricula_inicial, d.matricula_apos_censo, d.transferidos, d.cancelados, d.falecido, d.abandono, d.aprovados, d.reprovados, d.cursando, d.outras_situacoes FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id ORDER BY e.municipio, e.nome, d.ano"
                Press-Enter
            }
            "14" {
                $a = Read-Host "  Ano (ex: 2023)"
                if ($a -match '^\d+$') {
                    Export-DacCsv -BaseName "dac_join_${a}" -Sql "SELECT e.nome AS escola, e.municipio, d.ano, d.total_matriculas, d.matricula_inicial, d.matricula_apos_censo, d.transferidos, d.cancelados, d.falecido, d.abandono, d.aprovados, d.reprovados, d.cursando, d.outras_situacoes FROM dac_dados_escolares d JOIN dac_escolas e ON d.escola_id = e.id WHERE d.ano = $a ORDER BY e.municipio, e.nome"
                } else { Write-Host "  Ano invalido." -ForegroundColor Red }
                Press-Enter
            }
            "0" { return }
        }
    }
}

# =============================================================================
# BANCO DE DADOS (SQLite)
# =============================================================================

function Show-DatabaseMenu {
    while ($true) {
        Write-Header "BANCO DE DADOS (SQLite)"
        $dbFile = Join-Path $Script:ProjectRoot "backend\ucdb_ia.db"
        $sizeInfo = if (Test-Path $dbFile) {
            $kb = [math]::Round((Get-Item $dbFile).Length / 1KB, 1)
            "$kb KB"
        } else { "(nao existe)" }
        Write-Host "  Arquivo: backend/ucdb_ia.db  |  Tamanho: $sizeInfo" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  -- Backup / Restauracao --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [1]  Backup (copia do arquivo .db)"
        Write-Host "  [2]  Restaurar backup (.db)"
        Write-Host "  [3]  Exportar dump SQL (.sql)"
        Write-Line
        Write-Host "  -- Consultas rapidas --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [4]  Listar tabelas e contagem de registros"
        Write-Host "  [5]  Tamanhos das tabelas (estimativa)"
        Write-Host "  [6]  Ultimos 20 usuarios cadastrados"
        Write-Host "  [7]  Ultimas 20 mensagens"
        Write-Host "  [8]  Ultimos 20 logs de auditoria"
        Write-Host "  [9]  Consultas DAC  (escolas + dados escolares) >>" -ForegroundColor Cyan
        Write-Host "  [10] Executar SQL customizado"
        Write-Line
        Write-Host "  -- Manutencao --" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  [11] Criar tabelas (Base.metadata.create_all)"
        Write-Host "  [12] VACUUM (otimizar banco)"
        Write-Host "  [13] Apagar banco  [DESTRUTIVO]" -ForegroundColor DarkRed
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        switch ($choice) {
            "1" {
                if (-not (Test-Path $dbFile)) {
                    Write-Host "  Banco nao existe ainda." -ForegroundColor Red; Press-Enter; break
                }
                $ts   = Get-Date -Format "yyyyMMdd_HHmmss"
                $dest = Join-Path $Script:ProjectRoot "backup_ucdb_ia_${ts}.db"
                Copy-Item $dbFile $dest -Force
                Write-Host "  Backup salvo: $dest" -ForegroundColor Green; Press-Enter
            }
            "2" {
                $src = Read-Host "  Caminho do arquivo .db de backup"
                if (!(Test-Path $src)) { Write-Host "  Arquivo nao encontrado." -ForegroundColor Red; Press-Enter; break }
                if (Confirm-Action "Isso sobrescreve o banco atual. Continuar?") {
                    docker compose stop backend 2>&1 | Out-Null
                    Copy-Item $src $dbFile -Force
                    docker compose start backend 2>&1 | Out-Null
                    Write-Host "  Restauracao concluida." -ForegroundColor Green; Press-Enter
                }
            }
            "3" {
                if (-not (Test-Path $dbFile)) {
                    Write-Host "  Banco nao existe ainda." -ForegroundColor Red; Press-Enter; break
                }
                $ts   = Get-Date -Format "yyyyMMdd_HHmmss"
                $dest = Join-Path $Script:ProjectRoot "dump_ucdb_ia_${ts}.sql"
                $py = @"
import sqlite3
conn = sqlite3.connect('/app/ucdb_ia.db')
with open('/app/_dump_tmp.sql','w',encoding='utf-8') as f:
    for line in conn.iterdump(): f.write(line + '\n')
conn.close()
print('OK')
"@
                docker exec ucdb-backend python -c $py | Out-Null
                docker cp "ucdb-backend:/app/_dump_tmp.sql" $dest 2>&1 | Out-Null
                docker exec ucdb-backend rm -f /app/_dump_tmp.sql 2>&1 | Out-Null
                if (Test-Path $dest) {
                    Write-Host "  Dump salvo: $dest" -ForegroundColor Green
                } else {
                    Write-Host "  Falha ao gerar dump." -ForegroundColor Red
                }
                Press-Enter
            }
            "4" {
                $py = @"
import sqlite3
conn = sqlite3.connect('/app/ucdb_ia.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
tabs = [r[0] for r in cur.fetchall()]
if not tabs:
    print('  (nenhuma tabela)')
else:
    for t in tabs:
        try:
            cur.execute(f'SELECT COUNT(*) FROM \"{t}\"')
            c = cur.fetchone()[0]
            print(f'  {t:30s} {c:>10d} registro(s)')
        except Exception as e:
            print(f'  {t:30s}  erro: {e}')
conn.close()
"@
                docker exec ucdb-backend python -c $py
                Press-Enter
            }
            "5" {
                $py = @"
import sqlite3, os
db = '/app/ucdb_ia.db'
size = os.path.getsize(db)
print(f'  Arquivo total: {size/1024:.1f} KB ({size/1024/1024:.2f} MB)')
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
for (t,) in cur.fetchall():
    try:
        cur.execute(f'SELECT SUM(pgsize) FROM dbstat WHERE name=?',(t,))
        pg = cur.fetchone()[0] or 0
        print(f'  {t:30s} {pg/1024:>8.1f} KB')
    except Exception:
        cur.execute(f'SELECT COUNT(*) FROM \"{t}\"')
        print(f'  {t:30s} (dbstat indisponivel, {cur.fetchone()[0]} linhas)')
conn.close()
"@
                docker exec ucdb-backend python -c $py
                Press-Enter
            }
            "6"  {
                Invoke-Sqlite -Sql "SELECT external_id, full_name, role, course, is_blocked, created_at FROM users ORDER BY created_at DESC LIMIT 20"
                Press-Enter
            }
            "7"  {
                Invoke-Sqlite -Sql "SELECT id, conversation_id, role, substr(content,1,60) as conteudo, created_at FROM messages ORDER BY created_at DESC LIMIT 20"
                Press-Enter
            }
            "8"  {
                Invoke-Sqlite -Sql "SELECT activity, user_id, status, ip_address, timestamp FROM access_logs ORDER BY timestamp DESC LIMIT 20"
                Press-Enter
            }
            "9"  { Show-DacQueriesMenu }
            "10" {
                $sql = Read-Host "  SQL"
                Invoke-Sqlite -Sql $sql
                Press-Enter
            }
            "11" {
                Write-Host "  Criando tabelas no banco..." -ForegroundColor Cyan
                docker exec ucdb-backend python -c "from app.core.database import engine, Base; import app.api.models, app.dac.models; Base.metadata.create_all(bind=engine); print('Tabelas criadas / verificadas.')"
                Press-Enter
            }
            "12" {
                Write-Host "  Rodando VACUUM..." -ForegroundColor Cyan
                docker exec ucdb-backend python -c "import sqlite3; c=sqlite3.connect('/app/ucdb_ia.db'); c.execute('VACUUM'); c.close(); print('VACUUM concluido.')"
                Press-Enter
            }
            "13" {
                if (Confirm-Action "APAGAR o banco ucdb_ia.db permanentemente?") {
                    docker compose stop backend 2>&1 | Out-Null
                    if (Test-Path $dbFile) { Remove-Item $dbFile -Force }
                    docker compose start backend 2>&1 | Out-Null
                    Write-Host "  Banco apagado. Recrie as tabelas pela opcao [11]." -ForegroundColor Yellow
                    Press-Enter
                }
            }
            "0"  { return }
        }
    }
}

# =============================================================================
# USUARIOS E IMPORTACAO DE DADOS
# =============================================================================

function Show-UsersMenu {
    while ($true) {
        Write-Header "USUARIOS"
        Write-Host "  [1]  Criar/redefinir admin padrao (admin / admin123)"
        Write-Host "  [2]  Promover usuario para administrador"
        Write-Host "  [3]  Apagar usuario"
        Write-Host "  [4]  Listar todos os usuarios"
        Write-Host "  [5]  Desbloquear usuario (reset failed_attempts)"
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        switch ($choice) {
            "1" {
                Write-Host "  Executando create_admin.py..." -ForegroundColor Cyan
                docker exec ucdb-backend python -m utils.create_admin
                Press-Enter
            }
            "2" {
                $eid = Read-Host "  external_id do usuario a promover"
                if ($eid) {
                    $eid | docker exec -i ucdb-backend python -m utils.promote_admin
                }
                Press-Enter
            }
            "3" {
                $eid = Read-Host "  external_id do usuario a apagar"
                if ($eid -and (Confirm-Action "Apagar usuario '$eid' definitivamente?")) {
                    "$eid`ns" | docker exec -i ucdb-backend python -m utils.delete_user
                }
                Press-Enter
            }
            "4" {
                Invoke-Sqlite -Sql "SELECT external_id, full_name, role, course, is_blocked, failed_attempts, created_at FROM users ORDER BY created_at DESC"
                Press-Enter
            }
            "5" {
                $eid = Read-Host "  external_id do usuario a desbloquear"
                if ($eid) {
                    Invoke-Sqlite -Sql "UPDATE users SET is_blocked=0, failed_attempts=0 WHERE external_id='$eid'"
                }
                Press-Enter
            }
            "0" { return }
        }
    }
}

function Show-ImportMenu {
    while ($true) {
        Write-Header "IMPORTACAO DE DADOS (DAC)"
        $dataDir = Join-Path $Script:ProjectRoot "data"
        Write-Host "  Diretorio padrao de CSVs: data/" -ForegroundColor DarkGray
        Write-Host ""

        if (Test-Path $dataDir) {
            $csvs = @(Get-ChildItem -Path $dataDir -Filter "*.csv" -File -ErrorAction SilentlyContinue | Sort-Object Name)
            if ($csvs.Count -gt 0) {
                Write-Host "  CSVs encontrados:" -ForegroundColor Cyan
                $i = 1
                foreach ($f in $csvs) {
                    $kb = [math]::Round($f.Length / 1KB, 1)
                    Write-Host ("  [{0,2}]  {1,-45}  {2,8} KB" -f $i, $f.Name, $kb)
                    $i++
                }
                Write-Host ""
            } else {
                Write-Host "  Nenhum CSV encontrado em data/." -ForegroundColor Yellow
                Write-Host ""
            }
        } else {
            Write-Host "  Pasta data/ nao existe." -ForegroundColor Yellow
            Write-Host ""
        }

        Write-Host "  [A]  Importar TODOS os CSVs da pasta data/"
        Write-Host "  [N]  Importar um CSV pelo numero (lista acima)"
        Write-Host "  [P]  Informar caminho de um CSV manualmente"
        Write-Host "  [S]  Resumo do que ja foi importado (por ano)"
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"

        switch ($choice.ToUpper()) {
            "A" {
                if (-not (Test-Path $dataDir)) { Write-Host "  Pasta data/ nao existe." -ForegroundColor Red; Press-Enter; break }
                Write-Host "  Copiando CSVs para o container..." -ForegroundColor Cyan
                docker exec ucdb-backend mkdir -p /app/_csv_tmp 2>&1 | Out-Null
                foreach ($f in $csvs) {
                    docker cp $f.FullName "ucdb-backend:/app/_csv_tmp/$($f.Name)" 2>&1 | Out-Null
                }
                $py = @"
import os, glob
from app.core.database import SessionLocal, engine, Base
import app.api.models, app.dac.models
from app.dac.importer import importar_csv_bytes
Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    files = sorted(glob.glob('/app/_csv_tmp/*.csv'))
    for f in files:
        name = os.path.basename(f)
        with open(f,'rb') as fh: data = fh.read()
        try:
            r = importar_csv_bytes(data, name, db)
            r = r if isinstance(r, dict) else {'resultado': r}
            print(f'  [OK]  {name:40s} {r}')
        except Exception as e:
            print(f'  [ERR] {name}: {e}')
finally:
    db.close()
    import shutil; shutil.rmtree('/app/_csv_tmp', ignore_errors=True)
"@
                docker exec ucdb-backend python -c $py
                Press-Enter
            }
            "N" {
                $num = Read-Host "  Numero do CSV"
                $idx = 0
                if ([int]::TryParse($num,[ref]$idx) -and $idx -ge 1 -and $idx -le $csvs.Count) {
                    $file = $csvs[$idx-1].FullName
                    Import-SingleCsv -HostPath $file
                } else {
                    Write-Host "  Numero invalido." -ForegroundColor Red; Start-Sleep 1
                }
            }
            "P" {
                $file = Read-Host "  Caminho completo do CSV"
                if (Test-Path $file) { Import-SingleCsv -HostPath $file }
                else { Write-Host "  Arquivo nao encontrado." -ForegroundColor Red; Press-Enter }
            }
            "S" {
                Invoke-Sqlite -Sql "SELECT ano, COUNT(*) AS linhas, SUM(total_matriculas) AS matriculas FROM dac_dados_escolares GROUP BY ano ORDER BY ano"
                Press-Enter
            }
            "0" { return }
            default { }
        }
    }
}

function Import-SingleCsv {
    param([Parameter(Mandatory = $true)][string]$HostPath)
    $name = Split-Path $HostPath -Leaf
    Write-Host "  Copiando '$name' para o container..." -ForegroundColor Cyan
    docker cp $HostPath "ucdb-backend:/app/_import_tmp.csv" 2>&1 | Out-Null
    $py = @"
from app.core.database import SessionLocal, engine, Base
import app.api.models, app.dac.models
from app.dac.importer import importar_csv_bytes
Base.metadata.create_all(bind=engine)
with open('/app/_import_tmp.csv','rb') as f: data = f.read()
db = SessionLocal()
try:
    r = importar_csv_bytes(data, '$name', db)
    print(f'  Importado ($name): {r}')
except Exception as e:
    print(f'  ERRO: {e}')
finally:
    db.close()
import os; os.remove('/app/_import_tmp.csv')
"@
    docker exec ucdb-backend python -c $py
    Press-Enter
}

# =============================================================================
# INFORMACOES DO SISTEMA
# =============================================================================

function Show-Info {
    Write-Header "INFORMACOES DO SISTEMA"
    Write-Host "  ACESSO" -ForegroundColor Cyan
    Write-Host "  Frontend     ->  http://localhost:5173"
    Write-Host "  API REST     ->  http://localhost:8000"
    Write-Host "  API Docs     ->  http://localhost:8000/docs"
    Write-Host "  LLM Server   ->  http://localhost:8080"
    Write-Host "  Embeddings   ->  http://localhost:8081"
    Write-Host ""

    Write-Host "  CONFIGURACAO (.env)" -ForegroundColor Cyan
    $envFile = Join-Path $Script:ProjectRoot ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -notmatch "PASSWORD|SECRET|KEY" } |
            ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    } else {
        Write-Host "  .env nao encontrado -- usando defaults do docker-compose.yml" -ForegroundColor Yellow
    }
    Write-Host ""

    Write-Host "  IMAGENS DOCKER" -ForegroundColor Cyan
    docker images --format "  {{.Repository}}:{{.Tag}}  {{.Size}}  {{.CreatedSince}}" 2>$null |
        Where-Object { $_ -match "ucdb|nexus|llama" }
    Write-Host ""

    Write-Host "  VOLUMES" -ForegroundColor Cyan
    docker volume ls --filter "name=ucdb" --format "  {{.Name}}" 2>$null
    docker volume ls --filter "name=nexus" --format "  {{.Name}}" 2>$null
    Write-Host ""

    Write-Host "  USO DE DISCO DOCKER" -ForegroundColor Cyan
    docker system df 2>$null
    Write-Host ""

    Write-Host "  GPU (nvidia-smi)" -ForegroundColor Cyan
    $gpuFull = nvidia-smi 2>$null
    if ($gpuFull) { $gpuFull | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray } }
    else { Write-Host "  nvidia-smi nao disponivel." -ForegroundColor DarkGray }
    Write-Host ""

    Press-Enter
}

# =============================================================================
# LIMPEZA
# =============================================================================

function Show-CleanupMenu {
    while ($true) {
        Write-Header "LIMPEZA DOCKER"
        Write-Host "  [1]  Remover containers parados"
        Write-Host "  [2]  Remover imagens sem uso (dangling)"
        Write-Host "  [3]  Remover volumes sem uso"
        Write-Host "  [4]  Limpar cache de build"
        Write-Host "  [5]  Limpeza geral (docker system prune)"
        Write-Host "  [6]  Limpeza total com volumes  [DESTRUTIVO]" -ForegroundColor DarkRed
        Write-Host ""
        Write-Host "  [0]  Voltar" -ForegroundColor DarkGray
        Write-Host ""
        $choice = Read-Host "  Opcao"
        switch ($choice) {
            "1" { docker container prune -f; Press-Enter }
            "2" { docker image prune -f; Press-Enter }
            "3" { docker volume prune -f; Press-Enter }
            "4" { docker builder prune -f; Press-Enter }
            "5" {
                if (Confirm-Action "Remover containers/imagens/networks sem uso?") {
                    docker system prune -f; Press-Enter
                }
            }
            "6" {
                if (Confirm-Action "REMOVER TUDO incluindo volumes?") {
                    docker system prune -af --volumes; Press-Enter
                }
            }
            "0" { return }
        }
    }
}

# =============================================================================
# VERIFICACAO INICIAL
# =============================================================================

if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERRO: Docker nao encontrado. Instale o Docker Desktop." -ForegroundColor Red
    exit 1
}
$Script:NvidiaWarn = ""
if (!(nvidia-smi 2>$null)) { $Script:NvidiaWarn = "  [!] nvidia-smi nao encontrado -- monitoramento de GPU desabilitado." }

# =============================================================================
# MENU PRINCIPAL (loop persistente)
# =============================================================================

while ($true) {
    Write-Header
    Show-QuickStatus

    if ($Script:NvidiaWarn) { Write-Host $Script:NvidiaWarn -ForegroundColor DarkYellow; Write-Host "" }

    Write-Host "  SISTEMA" -ForegroundColor Cyan
    Write-Host "  [1]  Iniciar sistema completo"
    Write-Host "  [2]  Parar sistema"
    Write-Host "  [3]  Reiniciar sistema completo"
    Write-Host "  [4]  Iniciar com rebuild seletivo"
    Write-Host "  [5]  Parar e remover volumes  [DESTRUTIVO]" -ForegroundColor DarkRed
    Write-Line
    Write-Host "  DIAGNOSTICO" -ForegroundColor Cyan
    Write-Host "  [6]  Health check completo"
    Write-Host "  [7]  Monitoramento em tempo real"
    Write-Host "  [8]  Status detalhado (docker ps -a)"
    Write-Host "  [9]  Recursos snapshot (docker stats)"
    Write-Line
    Write-Host "  GERENCIAMENTO" -ForegroundColor Cyan
    Write-Host "  [10] Logs"
    Write-Host "  [11] Containers  (reiniciar / rebuild / shell)"
    Write-Host "  [12] Servidores de IA  (trocar modelo / restart / recarregar)"
    Write-Host "  [13] Banco de dados (SQLite)"
    Write-Host "  [14] Usuarios"
    Write-Host "  [15] Importacao de dados (DAC)"
    Write-Host "  [16] Limpeza Docker"
    Write-Line
    Write-Host "  [17] Informacoes completas do sistema" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [0]  Sair" -ForegroundColor DarkGray
    Write-Host ""

    $choice = Read-Host "  Opcao"

    switch ($choice) {
        "1"  { Start-Nexus }
        "2"  { if (Confirm-Action "Parar o sistema?") { Stop-Nexus } }
        "3"  { if (Confirm-Action "Reiniciar o sistema?") { Stop-Nexus; Start-Nexus } }
        "4"  {
            $sel = Show-RebuildSelector
            if ($sel) { Start-Nexus -Rebuild $sel }
        }
        "5"  { if (Confirm-Action "ATENCAO: Removera os volumes Docker. Confirmar?") { Stop-Nexus -WithVolumes } }
        "6"  { Invoke-HealthCheck }
        "7"  { Show-Monitoring }
        "8"  { docker ps -a; Press-Enter }
        "9"  { docker stats --no-stream; Press-Enter }
        "10" { Show-LogsMenu }
        "11" { Show-ContainerMenu }
        "12" { Show-LLMSelector }
        "13" { Show-DatabaseMenu }
        "14" { Show-UsersMenu }
        "15" { Show-ImportMenu }
        "16" { Show-CleanupMenu }
        "17" { Show-Info }
        "0"  { Write-Host "  Ate mais." -ForegroundColor DarkGray; exit 0 }
        default { Write-Host "  Opcao invalida." -ForegroundColor Red; Start-Sleep 1 }
    }
}
