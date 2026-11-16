$ErrorActionPreference = "Stop"

$buildRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Split-Path -Parent $buildRoot
$projectRoot = Split-Path -Parent $sourceRoot
$python = Join-Path $sourceRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "virtual env not found: $python" -ForegroundColor Red
    exit 1
}

$assets = Join-Path $sourceRoot "src\dshmanager\assets"
if (-not (Test-Path (Join-Path $assets 'dshmanager.ico'))) {
    Write-Host "generating icon ..."
    & $python (Join-Path $sourceRoot "dev/make_icon.py")
}

Push-Location $buildRoot
try {
    & $python -m PyInstaller --noconfirm --clean --distpath $buildRoot --workpath (Join-Path $env:TEMP "DSHManagerPyInstaller\build") "DSHManager.spec"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "build failed, exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

$built = Join-Path $buildRoot "DSHManager.exe"
$target = Join-Path $projectRoot "DSHManager.exe"
Copy-Item -Force $built $target
Write-Host ("OK: {0}" -f $target) -ForegroundColor Green
