#!/usr/bin/env bash
# Gera o "Tibia Overlay.app" — app macOS standalone, sem Terminal.
# Uso:  bash make_app.sh
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt pyinstaller

.venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name "Tibia Overlay" \
  --osx-bundle-identifier com.tibiaai.overlay \
  overlay.py

echo
echo "✅ Pronto: $(pwd)/dist/Tibia Overlay.app"
echo "Arraste para /Applications (ou rode direto do dist/)."
open dist 2>/dev/null || true
