[CmdletBinding()]
param(
    [switch]$Hardware,
    [switch]$Once,
    [switch]$ListAnimations,
    [switch]$NightSchedule,
    [double]$Fps,
    [double]$SecondsPerAnimation
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $PSScriptRoot ".venv"
$AnimationRoot = Join-Path $RepoRoot "common\animations"
$RequirementsStamp = Join-Path $VenvPath ".animation-requirements.sha256"

if ($env:OS -eq "Windows_NT") {
    $Python = Join-Path $VenvPath "Scripts\python.exe"
} else {
    $Python = Join-Path $VenvPath "bin\python"
}

if (-not (Test-Path $Python)) {
    Write-Host "Creating Pi animation virtual environment..."
    if ($env:OS -eq "Windows_NT" -and (Get-Command py -ErrorAction SilentlyContinue)) {
        & py -3 -m venv $VenvPath
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        & python3 -m venv $VenvPath
    } else {
        & python -m venv $VenvPath
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the animation virtual environment." }
}

$DependencyFiles = @()
if ($Hardware) {
    $DependencyFiles += Join-Path $PSScriptRoot "requirements.txt"
}
if (Test-Path $AnimationRoot) {
    $DependencyFiles += Get-ChildItem -Path $AnimationRoot -Filter "requirements*.txt" -File -Recurse |
        Select-Object -ExpandProperty FullName
}
$DependencyFiles = @($DependencyFiles | Sort-Object -Unique)

$FingerprintParts = @()
foreach ($RequirementsFile in $DependencyFiles) {
    if (-not (Test-Path $RequirementsFile)) { throw "Missing dependency file: $RequirementsFile" }
    $Hash = (Get-FileHash $RequirementsFile -Algorithm SHA256).Hash
    $FingerprintParts += "$RequirementsFile=$Hash"
}
$FingerprintText = [string]::Join("`n", $FingerprintParts)
$Hasher = [System.Security.Cryptography.SHA256]::Create()
$Fingerprint = [BitConverter]::ToString(
    $Hasher.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($FingerprintText))
).Replace("-", "")
$Hasher.Dispose()
$InstalledFingerprint = if (Test-Path $RequirementsStamp) {
    (Get-Content $RequirementsStamp -Raw).Trim()
} else {
    ""
}

if ($InstalledFingerprint -ne $Fingerprint) {
    foreach ($RequirementsFile in $DependencyFiles) {
        Write-Host "Installing animation dependencies from $RequirementsFile..."
        & $Python -m pip install -r $RequirementsFile
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed: $RequirementsFile" }
    }
    Set-Content -Path $RequirementsStamp -Value $Fingerprint -NoNewline -Encoding ascii
}

$EnginePath = Join-Path $PSScriptRoot "3dXmasTree.py"
$EngineArguments = @($EnginePath)
if ($PSBoundParameters.ContainsKey("Fps")) {
    $EngineArguments += @("--fps", "$Fps")
}
if ($PSBoundParameters.ContainsKey("SecondsPerAnimation")) {
    $EngineArguments += @("--seconds-per-animation", "$SecondsPerAnimation")
}
if ($Hardware) { $EngineArguments += "--hardware" }
if ($Once) { $EngineArguments += "--once" }
if ($ListAnimations) { $EngineArguments += "--list-animations" }
if ($NightSchedule) { $EngineArguments += "--night-schedule" }

Write-Host "Starting Pi animation engine..."
& $Python @EngineArguments
if ($LASTEXITCODE -ne 0) { throw "Pi animation engine exited with code $LASTEXITCODE." }
