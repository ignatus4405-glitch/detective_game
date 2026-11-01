# Build script for Windows (PowerShell)
# Usage: .\tools\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "=== Detective: Blackville — Build ===" -ForegroundColor Cyan
$VERSION = (Get-Content VERSION).Trim()
Write-Host "Version: $VERSION"

# Install deps
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Tests
pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

# Clean
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }

# Build
pyinstaller --name DetectiveBlackville --onefile --windowed --clean --noconfirm `
  --add-data "src/detective_game/assets;detective_game/assets" `
  --add-data "src/detective_game/cases;detective_game/cases" `
  --hidden-import pygame `
  --collect-all pygame `
  src/detective_game/main.py

if (-not (Test-Path dist/DetectiveBlackville.exe)) { throw "Build failed — exe not found" }

# latest.json
$json = @"
{
  "version": "$VERSION",
  "tag": "v$VERSION",
  "url": "https://github.com/ignatus4405-glitch/detective_game/releases/tag/v$VERSION",
  "published_at": "$(Get-Date -Format o)",
  "notes": "Local build $VERSION"
}
"@
$json | Out-File -Encoding utf8 dist/latest.json

# Zip
Compress-Archive -Path dist/DetectiveBlackville.exe,dist/latest.json -DestinationPath DetectiveBlackville-Windows.zip -Force
Write-Host "✓ Build complete: dist/DetectiveBlackville.exe" -ForegroundColor Green
Write-Host "✓ Zip: DetectiveBlackville-Windows.zip" -ForegroundColor Green
Get-ChildItem dist, DetectiveBlackville-Windows.zip | Format-Table Name, Length
