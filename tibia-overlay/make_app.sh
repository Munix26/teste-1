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

# Assinatura estável: com um certificado local "Tibia Overlay Dev" no chaveiro,
# todo build sai com a MESMA identidade e a permissão de Gravação de Tela
# sobrevive aos rebuilds (sem ele, o macOS trata cada build como app novo).
IDENTITY="Tibia Overlay Dev"
if security find-identity -p codesigning -v 2>/dev/null | grep -q "$IDENTITY"; then
  codesign --force --deep --sign "$IDENTITY" "dist/Tibia Overlay.app"
  echo "🔏 Assinado com '$IDENTITY' — permissão de tela persiste entre builds."
else
  echo "ℹ️  Sem certificado '$IDENTITY' no chaveiro — assinatura ad-hoc (a"
  echo "   permissão de Gravação de Tela precisará ser re-concedida a cada"
  echo "   build). Para criar uma vez: Acesso às Chaves → menu Acesso às"
  echo "   Chaves → Assistente de Certificado → Criar um Certificado…"
  echo "   Nome: Tibia Overlay Dev | Auto-assinado raiz | Assinatura de código."
fi

echo
echo "✅ Pronto: $(pwd)/dist/Tibia Overlay.app"
echo "Arraste para /Applications (ou rode direto do dist/)."
open dist 2>/dev/null || true
