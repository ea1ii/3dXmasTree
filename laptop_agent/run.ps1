$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $PSScriptRoot ".venv"
$Python = Join-Path $VenvPath "Scripts\python.exe"
$Requirements = Join-Path $PSScriptRoot "requirements.txt"
$RequirementsStamp = Join-Path $VenvPath ".requirements.sha256"

if (-not (Test-Path $Python)) {
    Write-Host "Creating laptop virtual environment..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $VenvPath
    } else {
        & python -m venv $VenvPath
    }
}

$RequirementsHash = (Get-FileHash $Requirements -Algorithm SHA256).Hash
$InstalledHash = if (Test-Path $RequirementsStamp) { (Get-Content $RequirementsStamp -Raw).Trim() } else { "" }
if ($InstalledHash -ne $RequirementsHash) {
    Write-Host "Installing laptop requirements..."
    & $Python -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "Laptop dependency installation failed." }
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
        $SecureToken = Read-Host "Paste the shared PC agent token" -AsSecureString
        $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
        try {
            $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
        }
        if ([string]::IsNullOrWhiteSpace($Token)) { throw "The shared agent token is empty." }
        Set-Content -Path $TokenPath -Value $Token -NoNewline -Encoding ascii
    }
} else {
    Set-Content -Path $TokenPath -Value $Token -NoNewline -Encoding ascii
}
$env:XMAS_AGENT_TOKEN = $Token

Write-Host "Starting laptop camera agent..."
& $Python (Join-Path $PSScriptRoot "camera_server.py")
if ($LASTEXITCODE -ne 0) { throw "Laptop camera agent exited with code $LASTEXITCODE." }
