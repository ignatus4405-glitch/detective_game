# Build script for Windows (PowerShell) — ИСПРАВЛЕННАЯ ВЕРСИЯ
# Исправляет ошибку: attempted relative import with no known parent package
# Использует launcher.py как точку входа + добавляет manifest/version для SmartScreen
$ErrorActionPreference = "Stop"

Write-Host "=== Detective: Blackville — Build ===" -ForegroundColor Cyan
$VERSION = (Get-Content VERSION).Trim().TrimStart('v')
Write-Host "Version: $VERSION"

# Генерация version_info и manifest с текущей версией
Write-Host "Generating version_info with $VERSION..." -ForegroundColor Yellow
python tools/generate_version_info.py
if ($LASTEXITCODE -ne 0) { throw "generate_version_info failed" }

# Убедимся что файлы сгенерированы
$VersionFile = "build_version_info.txt"
$ManifestFile = "build_app.manifest"
if (-not (Test-Path $VersionFile)) { Write-Warning "No $VersionFile, using fallback"; $VersionFile = "tools/version_info.txt" }
if (-not (Test-Path $ManifestFile)) { Write-Warning "No $ManifestFile, using fallback"; $ManifestFile = "tools/app.manifest" }

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
if (Test-Path DetectiveBlackville.spec) { Remove-Item -Force DetectiveBlackville.spec }

# Build — ИСПРАВЛЕНО: используем launcher.py вместо src/detective_game/main.py
# Ключевые флаги для SmartScreen:
#  --version-file — метаданные (CompanyName, ProductVersion) — снижает флаг SmartScreen
#  --manifest — trustInfo asInvoker (не запрашивает UAC)
#  --icon — иконка повышает доверие
#  --collect-all detective_game — явно собираем пакет
Write-Host "Building exe via launcher.py..." -ForegroundColor Cyan
pyinstaller --name DetectiveBlackville --onefile --windowed --clean --noconfirm `
  --paths src `
  --hidden-import detective_game `
  --hidden-import detective_game.main `
  --hidden-import detective_game.config `
  --hidden-import detective_game.data `
  --hidden-import detective_game.game_state `
  --hidden-import detective_game.save_system `
  --hidden-import detective_game.updater `
  --hidden-import detective_game.ui.widgets `
  --collect-all pygame `
  --collect-all detective_game `
  --add-data "src/detective_game/assets;detective_game/assets" `
  --add-data "src/detective_game/cases;detective_game/cases" `
  --icon "src/detective_game/assets/images/icon.ico" `
  --version-file $VersionFile `
  --manifest $ManifestFile `
  --uac-admin false `
  launcher.py

if (-not (Test-Path dist/DetectiveBlackville.exe)) { throw "Build failed — exe not found" }

# Проверка: размер и подпись
$exe = Get-Item dist/DetectiveBlackville.exe
Write-Host "✓ Exe built: $($exe.Length / 1MB) MB" -ForegroundColor Green

# Создаем README для игрока с инструкцией по SmartScreen
python tools/make_readme.py

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

# Hash для проверки целостности (помогает при SmartScreen — пользователь видит что файл не модифицирован)
$hash = (Get-FileHash dist/DetectiveBlackville.exe -Algorithm SHA256).Hash
"SHA256: $hash  DetectiveBlackville.exe" | Out-File -Encoding utf8 dist/SHA256SUMS.txt
Write-Host "SHA256: $hash" -ForegroundColor DarkGray

# Zip
Compress-Archive -Path dist/DetectiveBlackville.exe,dist/latest.json,dist/SHA256SUMS.txt,dist/README.txt -DestinationPath DetectiveBlackville-Windows.zip -Force -ErrorAction SilentlyContinue
# fallback если README.txt не создался
if (-not (Test-Path DetectiveBlackville-Windows.zip)) {
  Compress-Archive -Path dist/DetectiveBlackville.exe,dist/latest.json -DestinationPath DetectiveBlackville-Windows.zip -Force
}
Write-Host "✓ Build complete: dist/DetectiveBlackville.exe" -ForegroundColor Green
Write-Host "✓ Zip: DetectiveBlackville-Windows.zip" -ForegroundColor Green
Write-Host "✓ Если SmartScreen ругается — см. docs/SMARTSCREEN.md" -ForegroundColor Yellow
Get-ChildItem dist, DetectiveBlackville-Windows.zip | Format-Table Name, Length

# Инструкция
Write-Host ""
Write-Host "=== SmartScreen: если Windows блокирует запуск ===" -ForegroundColor Yellow
Write-Host "1. Правый клик по exe → Свойства → Поставьте галочку 'Разблокировать' внизу (если есть)"
Write-Host "2. При запуске: 'Защита Windows' → Подробнее → Выполнить в любом случае"
Write-Host "3. Или используйте установщик: tools/installer.iss → DetectiveBlackville-Setup.exe (меньше ложных срабатываний)"
Write-Host "Подробнее: docs/SMARTSCREEN.md"
