$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $PSScriptRoot ".venv"
$Python = Join-Path $VenvPath "Scripts\python.exe"
$Requirements = Join-Path $RepoRoot "requirements.txt"
$RequirementsStamp = Join-Path $VenvPath ".requirements.sha256"

if (-not (Test-Path $Python)) {
    Write-Host "Creating PC virtual environment..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $VenvPath
    } else {
        & python -m venv $VenvPath
    }
}

$RequirementsHash = (Get-FileHash $Requirements -Algorithm SHA256).Hash
$InstalledHash = if (Test-Path $RequirementsStamp) { (Get-Content $RequirementsStamp -Raw).Trim() } else { "" }
if ($InstalledHash -ne $RequirementsHash) {
    Write-Host "Installing PC requirements..."
    & $Python -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "PC dependency installation failed." }
    Set-Content -Path $RequirementsStamp -Value $RequirementsHash -NoNewline -Encoding ascii
}

$TokenDirectory = Join-Path $env:LOCALAPPDATA "3dXmasTree"
$TokenPath = Join-Path $TokenDirectory "agent-token.txt"
New-Item -ItemType Directory -Path $TokenDirectory -Force | Out-Null
$Token = $env:XMAS_AGENT_TOKEN
if ([string]::IsNullOrWhiteSpace($Token)) {
    if (Test-Path $TokenPath) {
        $Token = (Get-Content $TokenPath -Raw).Trim()
    } else {
        $Token = [guid]::NewGuid().ToString("N")
        Set-Content -Path $TokenPath -Value $Token -NoNewline -Encoding ascii
        Write-Host "Created the shared agent token. Enter this same value once on the laptop and Pi:"
        Write-Host $Token
    }
} else {
    Set-Content -Path $TokenPath -Value $Token -NoNewline -Encoding ascii
}
if ([string]::IsNullOrWhiteSpace($Token)) { throw "The shared agent token is empty." }
$env:XMAS_AGENT_TOKEN = $Token

Write-Host "Starting PC command center..."
& $Python (Join-Path $PSScriptRoot "main.py")
if ($LASTEXITCODE -ne 0) { throw "PC command center exited with code $LASTEXITCODE." }