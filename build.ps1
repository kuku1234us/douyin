Param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

Write-Host "== DouyinFramework build =="
Write-Host "Using Poetry environment (poetry run)"

if ($Clean) {
    Write-Host "Cleaning previous build artifacts..."
    Remove-Item -Recurse -Force build, dist, '.\DouyinFramework.spec.cache' -ErrorAction SilentlyContinue
}

Write-Host "Checking PyInstaller availability..."
poetry run python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller into Poetry venv..."
    poetry run python -m pip install --upgrade pip
    poetry run python -m pip install pyinstaller
}

$png = Join-Path "douyin_app" "resources\douyin.png"
$ico = Join-Path "douyin_app" "resources\douyin.ico"
if (Test-Path $png) {
    Write-Host "Converting PNG to ICO for Windows executable icon..."
    $conv = @"
from PIL import Image
import sys
png_path, ico_path = sys.argv[1], sys.argv[2]
img = Image.open(png_path)
sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(24,24),(16,16)]
img.save(ico_path, format='ICO', sizes=sizes)
"@
    $tmp = Join-Path $env:TEMP "png2ico_$([System.Guid]::NewGuid().ToString('N')).py"
    Set-Content -LiteralPath $tmp -Value $conv -Encoding UTF8
    poetry run python $tmp $png $ico
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path $ico)) {
        Write-Warning "ICO conversion failed; the EXE may not have a custom icon."
    }
} else {
    Write-Warning "PNG icon not found at $png; skipping ICO generation."
}

$spec = "DouyinFramework.spec"
if (-not (Test-Path $spec)) {
    Write-Error "Spec file not found: $spec"
    exit 1
}

Write-Host "Running PyInstaller with $spec ..."
poetry run pyinstaller $spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

$exeOneFile = Join-Path "dist" "DouyinFramework.exe"
$exeOneDir  = Join-Path "dist" "DouyinFramework\DouyinFramework.exe"
if (Test-Path $exeOneFile) {
    Write-Host "Build succeeded: $exeOneFile"
} elseif (Test-Path $exeOneDir) {
    Write-Host "Build succeeded: $exeOneDir"
} else {
    Write-Warning "Build finished but executable not found in dist/."
}

Write-Host "Done."


