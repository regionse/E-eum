# 이음 — 백엔드/프론트 재시작 (Windows PowerShell)
#
#   .\restart.ps1              백엔드만 (제일 흔한 경우)
#   .\restart.ps1 -Front       프론트도 같이
#   .\restart.ps1 -Build       프론트를 dev 대신 build (배포 직전)
#   .\restart.ps1 -Stop        둘 다 끄기만
#
# ── 무엇이 재시작으로 반영되고, 무엇이 안 되는가 ──────────────────────
#   반영됨   파이썬/JSX **코드** 변경 · .env 변경
#   반영 안 됨
#     · DB 데이터        → RDS 를 직접 고치거나 최신화 스크립트를 돌려야 한다
#                          (재시작은 DB 를 건드리지 않는다)
#     · Pinecone 벡터    → MySQL 을 고쳐도 벡터는 그대로다. embed_* 를 다시 돌려야 한다
#     · frontend/dist    → 배포본은 npm run build 를 해야 바뀐다 (dev 서버와 별개)
#
# ※ DB 는 .env 의 DB_HOST 를 따라간다. 지금은 AWS RDS 를 가리키고 있으므로
#   여기서 무엇을 하든 **운영 데이터**에 반영된다. 팀에 알리고 쓸 것.

param(
    [switch]$Front,     # 프론트도 재시작
    [switch]$Build,     # 프론트를 build (dev 대신)
    [switch]$Stop       # 끄기만
)

$ErrorActionPreference = 'Continue'
$Root    = $PSScriptRoot
$Backend = Join-Path $Root 'Backend'
$Web     = Join-Path $Root 'frontend'
$LogDir  = Join-Path $Root '.logs'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Stop-OnPort($port, $label) {
    #  포트를 잡고 있는 프로세스만 정확히 죽인다.
    #  ⚠ `Get-Process python | Stop-Process` 같은 건 쓰지 않는다 —
    #    다른 파이썬 작업(배치·측정 스크립트)까지 같이 죽는다. 실제로 그런 사고가 있었다.
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "  $label : 이미 꺼져 있음 (포트 $port)"; return }
    foreach ($procId in ($conns.OwningProcess | Select-Object -Unique)) {
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Stop-Process -Id $procId -Force
            Write-Host "  $label : 종료 (PID $procId · $($p.ProcessName))"
        } catch {
            Write-Host "  $label : PID $procId 종료 실패 — $($_.Exception.Message)"
        }
    }
    Start-Sleep -Milliseconds 700
}

function Wait-Port($port, $label, $seconds = 25) {
    for ($i = 0; $i -lt $seconds; $i++) {
        Start-Sleep -Seconds 1
        if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
            Write-Host "  $label : 준비됨 ($($i + 1)초)"
            return $true
        }
    }
    Write-Host "  $label : $seconds 초 안에 안 뜸 — 로그를 보세요"
    return $false
}

Write-Host ''
Write-Host '== 이음 재시작 =='

# ── 끄기 ──────────────────────────────────────────────────────────
Stop-OnPort 8000 '백엔드'
if ($Front -or $Build -or $Stop) { Stop-OnPort 5173 '프론트' }
if ($Stop) { Write-Host ''; Write-Host '  (끄기만 하고 종료)'; Write-Host ''; exit 0 }

# ── 백엔드 ────────────────────────────────────────────────────────
#  PYTHONIOENCODING=utf-8 필수 — 없으면 로그의 한글에서 cp949 오류로 턴이 죽는다(실측).
$env:PYTHONIOENCODING = 'utf-8'
$beOut = Join-Path $LogDir 'backend.log'
$beErr = Join-Path $LogDir 'backend.err.log'
Start-Process -FilePath 'python' `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8000' `
    -WorkingDirectory $Backend -WindowStyle Hidden `
    -RedirectStandardOutput $beOut -RedirectStandardError $beErr
Write-Host '  백엔드 : 시작함 (포트 8000)'
Wait-Port 8000 '백엔드' | Out-Null

# ── 프론트 ────────────────────────────────────────────────────────
if ($Build) {
    Write-Host '  프론트 : build 중...'
    Push-Location $Web
    npm run build
    Pop-Location
    Write-Host '  프론트 : dist 갱신됨 (배포본)'
} elseif ($Front) {
    $feOut = Join-Path $LogDir 'frontend.log'
    $feErr = Join-Path $LogDir 'frontend.err.log'
    Start-Process -FilePath 'cmd' -ArgumentList '/c', 'npm run dev' `
        -WorkingDirectory $Web -WindowStyle Hidden `
        -RedirectStandardOutput $feOut -RedirectStandardError $feErr
    Write-Host '  프론트 : 시작함 (포트 5173)'
    Wait-Port 5173 '프론트' | Out-Null
}

Write-Host ''
Write-Host "  로그 : $LogDir"
Write-Host '  확인 : python -m tools.db_status   (Backend 에서 — RDS 현황)'
Write-Host ''
