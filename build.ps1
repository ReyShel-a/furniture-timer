# Build dist/FurnitureTimer.exe (onefile, windowed).
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

& $python -m pip install -e ".[build]"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python -m PyInstaller --noconfirm --clean furniture_timer.spec
exit $LASTEXITCODE
