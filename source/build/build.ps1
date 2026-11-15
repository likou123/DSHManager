$ErrorActionPreference = "Stop"

$buildRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceRoot = Split-Path -Parent $buildRoot
$projectRoot = Split-Path -Parent $sourceRoot
$python = Join-Path $sourceRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "virtual env not found: $python" -ForegroundColor Red
    Write-Host "run: python -m venv .venv && pip install -r build/requirements.txt" -ForegroundColor Yellow
    exit 1
}

$assets = Join-Path $sourceRoot "src\dshmanager\assets"

# Icon is a build artifact: generate it from the DSH executable when missing
$icoPath = Join-Path $assets "dshmanager.ico"
$pngPath = Join-Path $assets "dshmanager.png"
if (-not (Test-Path $icoPath) -or -not (Test-Path $pngPath)) {
    Write-Host "generating icon ..."
    & $python (Join-Path $sourceRoot "dev/make_icon.py")
}

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "DSHManager",
    "--icon", $icoPath,
    "--add-data", ("{0};dshmanager/assets" -f $icoPath),
    "--add-data", ("{0};dshmanager/assets" -f $pngPath),
    "--paths", (Join-Path $sourceRoot "src"),
    "--distpath", $buildRoot,
    "--workpath", (Join-Path $env:TEMP "DSHManagerPyInstaller\build"),
    "--specpath", (Join-Path $env:TEMP "DSHManagerPyInstaller\spec"),
    (Join-Path $sourceRoot "run_dshmanager.py")
)

& $python @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "build failed, exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

$built = Join-Path $buildRoot "DSHManager.exe"
$target = Join-Path $projectRoot "DSHManager.exe"
Copy-Item -Force $built $target
Write-Host ("OK: {0}" -f $target) -ForegroundColor Green
