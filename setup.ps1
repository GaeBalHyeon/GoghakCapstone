$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonCandidates = @(
    "C:\Users\Ria\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    "python.exe",
    "py.exe"
)
$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    try {
        & $candidate --version *> $null
        if ($LASTEXITCODE -eq 0) { $pythonExe = $candidate; break }
    } catch { }
}
if (-not $pythonExe) {
    throw "Python 3를 찾지 못했습니다. Python 3.11 이상을 설치한 뒤 다시 실행하세요."
}

if (-not (Test-Path ".venv")) {
    & $pythonExe -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
Write-Host "설치 완료. .\run.ps1 로 실행하세요." -ForegroundColor Green

