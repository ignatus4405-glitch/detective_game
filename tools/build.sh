#!/usr/bin/env bash
set -e
echo "=== Detective: Blackville — Build (Linux/macOS) ==="
VERSION=$(cat VERSION | tr -d ' \n\r' | sed 's/^v//')
echo "Version: $VERSION"

pip install -r requirements.txt
pip install pyinstaller

pytest -q

rm -rf dist build

pyinstaller --name DetectiveBlackville --onefile --windowed --clean --noconfirm \
  --add-data "src/detective_game/assets:detective_game/assets" \
  --add-data "src/detective_game/cases:detective_game/cases" \
  --hidden-import pygame \
  --collect-all pygame \
  src/detective_game/main.py

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

zip -r DetectiveBlackville-Windows.zip dist/DetectiveBlackville dist/latest.json 2>/dev/null || zip -r DetectiveBlackville-Windows.zip dist/
echo "✓ Build complete"
ls -lh dist/ DetectiveBlackville-Windows.zip
