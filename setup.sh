#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║       Mac Voice — Setup          ║"
echo "  ║  Local dictation with Whisper    ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: Mac Voice only works on macOS."
    exit 1
fi

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install it with: brew install python3"
    exit 1
fi

echo "[1/4] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Created venv"
else
    echo "  ✓ venv already exists"
fi

echo "[2/4] Installing dependencies..."
venv/bin/pip install -q -r requirements.txt
echo "  ✓ Dependencies installed"

echo "[3/3] Downloading Whisper large-v3 model..."
MODEL_DIR="$SCRIPT_DIR/models"
MODEL_FILE="$MODEL_DIR/ggml-large-v3.bin"

if [ ! -f "$MODEL_FILE" ]; then
    echo "  Downloading ~3GB model (this will take a few minutes)..."
    mkdir -p "$MODEL_DIR"
    curl -L --progress-bar \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin" \
        -o "$MODEL_FILE"
    echo "  ✓ Model downloaded"
else
    echo "  ✓ Model already downloaded"
fi

# Add alias to shell config
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

ALIAS_CMD="alias voice='${SCRIPT_DIR}/venv/bin/python ${SCRIPT_DIR}/app.py'"

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "mac-voice" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Mac Voice - local dictation tool" >> "$SHELL_RC"
        echo "$ALIAS_CMD" >> "$SHELL_RC"
        echo "  ✓ Added 'voice' alias to $SHELL_RC"
    else
        echo "  ✓ 'voice' alias already in $SHELL_RC"
    fi
fi

echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║        Setup complete!           ║"
echo "  ╚══════════════════════════════════╝"
echo ""
echo "  To start:  source $SHELL_RC && voice"
echo "  Hotkey:    ⌘⇧1 (Cmd+Shift+1)"
echo "  Stop:      Ctrl+C"
echo ""
echo "  ⚠️  First run: macOS will ask for permissions."
echo "  Grant these in System Settings → Privacy & Security:"
echo ""
echo "    1. Microphone        (prompted automatically)"
echo "    2. Accessibility     (add your Terminal app)"
echo "    3. Input Monitoring  (add your Terminal app)"
echo ""
