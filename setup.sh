#!/bin/bash
set -e

PYTHON=/opt/homebrew/bin/python3.13

echo "HomenetMon — prerequisite setup"
echo "================================"

# ── 1. Xcode command-line tools ───────────────────────────────────────────────
echo ""
echo "[1/4] Checking Xcode command-line tools..."
if ! xcode-select -p &>/dev/null; then
    echo "  Installing Xcode command-line tools (a dialog will appear)..."
    xcode-select --install
    echo "  Re-run this script once the installation completes."
    exit 0
else
    echo "  ✓ Already installed"
fi

# ── 2. Homebrew ───────────────────────────────────────────────────────────────
echo ""
echo "[2/4] Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for the rest of this script (Apple Silicon path)
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "  ✓ Already installed ($(brew --version | head -1))"
fi

# ── 3. Python 3.13 + tkinter ─────────────────────────────────────────────────
echo ""
echo "[3/4] Checking Python 3.13 and tkinter..."
if ! [ -f "$PYTHON" ]; then
    echo "  Installing python@3.13..."
    brew install python@3.13
else
    echo "  ✓ python@3.13 already installed"
fi

if ! brew list python-tk@3.13 &>/dev/null; then
    echo "  Installing python-tk@3.13..."
    brew install python-tk@3.13
else
    echo "  ✓ python-tk@3.13 already installed"
fi

# Verify tkinter works
if ! $PYTHON -c "import tkinter" &>/dev/null; then
    echo ""
    echo "  ERROR: tkinter still not working after install."
    echo "  Try: brew reinstall python-tk@3.13"
    exit 1
fi

# ── 4. Python packages ────────────────────────────────────────────────────────
echo ""
echo "[4/4] Installing Python packages..."
$PYTHON -m pip install -r requirements.txt --break-system-packages --quiet
echo "  ✓ customtkinter, matplotlib, psutil installed"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "================================"
echo "Setup complete. To run the app:"
echo ""
echo "  $PYTHON app.py"
echo ""
