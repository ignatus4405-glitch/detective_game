#!/usr/bin/env bash
set -e
echo "=== Detective: Blackville — Build (Linux/macOS) ==="
VERSION=$(cat VERSION | tr -d ' \n\r' | sed 's/^v//')
echo "Version: $VERSION"

# Генерация version_info (если на Linux — всё равно генерируем для консистентности)
python3 tools/generate_version_info.py || echo "generate_version_info fallback"

pip install -r requirements.txt
pip install pyinstaller

pytest -q

rm -rf dist build *.spec

# ИСПРАВЛЕНО: launcher.py вместо src/detective_game/main.py
pyinstaller --name DetectiveBlackville --onefile --windowed --clean --noconfirm \
  --paths src \
  --hidden-import detective_game \
  --hidden-import detective_game.main \
  --collect-all pygame \
  --collect-all detective_game \
  --add-data "src/detective_game/assets:detective_game/assets" \
  --add-data "src/detective_game/cases:detective_game/cases" \
  --add-data "VERSION:." \
  --add-data "VERSION:detective_game" \
  --hidden-import detective_game._build_version \
  launcher.py

if [ ! -f dist/DetectiveBlackville ]; then
  echo "Build failed"
  exit 1
fi

cat > dist/latest.json <<EOF
{
  "version": "$VERSION",
  "tag": "v$VERSION",
  "url": "https://github.com/ignatus4405-glitch/detective_game/releases/tag/v$VERSION",
  "published_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "notes": "Local build $VERSION"
}
EOF

python3 tools/make_readme.py || true

# SHA256
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum dist/DetectiveBlackville > dist/SHA256SUMS.txt
  cat dist/SHA256SUMS.txt
fi

zip -r DetectiveBlackville-Windows.zip dist/DetectiveBlackville dist/latest.json 2>/dev/null || zip -r DetectiveBlackville-Windows.zip dist/
echo "✓ Build complete"
ls -lh dist/ DetectiveBlackville-Windows.zip
echo "SmartScreen: см. docs/SMARTSCREEN.md"
