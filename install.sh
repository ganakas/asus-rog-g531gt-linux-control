#!/bin/bash
# ASUS ROG Strix G531GT — Linux Control
# Installer

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
step() { echo -e "\n${BOLD}$1${NC}"; }

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   ASUS ROG G531GT — Linux Control        ║"
echo "  ║   Fan control + Keyboard backlight        ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Must run as regular user (not root), but with sudo available
if [ "$EUID" -eq 0 ]; then
    fail "Don't run as root. Run as your normal user: bash install.sh"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1. Check dependencies ─────────────────────────────────────────────────────
step "Checking dependencies..."

check_cmd() {
    if command -v "$1" &>/dev/null; then
        ok "$1"
    else
        warn "$1 not found — $2"
        MISSING_DEPS=1
    fi
}

check_pkg() {
    if python3 -c "import gi; gi.require_version('$2', '$3'); from gi.repository import $2" &>/dev/null 2>&1; then
        ok "$1"
    else
        warn "$1 not found (install: sudo apt install $4)"
        MISSING_DEPS=1
    fi
}

MISSING_DEPS=0
check_cmd python3 "install: sudo apt install python3"
check_cmd nvidia-smi "needed for GPU temp — install NVIDIA drivers"
check_cmd sensors "install: sudo apt install lm-sensors"
check_pkg "GTK 4" Gtk 4.0 python3-gi
check_pkg "libadwaita" Adw 1 gir1.2-adw-1

if [ "$MISSING_DEPS" -eq 1 ]; then
    echo ""
    warn "Some dependencies are missing. The app may not work fully."
    read -rp "  Continue anyway? [y/N] " yn
    [[ "$yn" =~ ^[Yy]$ ]] || exit 0
fi

# ── 2. Install system scripts ─────────────────────────────────────────────────
step "Installing system scripts..."

sudo cp "$SCRIPT_DIR/asus-fan-control.sh"  /usr/local/bin/asus-fan-control.sh
sudo chmod +x /usr/local/bin/asus-fan-control.sh
ok "asus-fan-control.sh → /usr/local/bin/"

sudo cp "$SCRIPT_DIR/asus-kbd-backlight" /usr/local/bin/asus-kbd-backlight
sudo chmod +x /usr/local/bin/asus-kbd-backlight
ok "asus-kbd-backlight → /usr/local/bin/"

# ── 3. Load acpi_call module ──────────────────────────────────────────────────
step "Loading kernel module..."

if ! lsmod | grep -q acpi_call; then
    sudo modprobe acpi_call 2>/dev/null && ok "acpi_call loaded" || warn "acpi_call not available (fan control may not work)"
else
    ok "acpi_call already loaded"
fi

# Persist across reboots
if ! grep -q acpi_call /etc/modules 2>/dev/null; then
    echo acpi_call | sudo tee -a /etc/modules > /dev/null
    ok "acpi_call added to /etc/modules"
fi

# ── 4. Install & enable systemd service ──────────────────────────────────────
step "Enabling systemd service..."

sudo cp "$SCRIPT_DIR/asus-fan-control.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asus-fan-control
ok "asus-fan-control.service enabled and started"

# ── 5. Install the app ────────────────────────────────────────────────────────
step "Installing app..."

APP_DIR="$HOME/.local/share/asus-fan-control"
mkdir -p "$APP_DIR"
cp "$SCRIPT_DIR/fan-control.py" "$APP_DIR/fan-control.py"
ok "App installed to $APP_DIR"

# Desktop launcher
DESKTOP_FILE="$HOME/.local/share/applications/asus-fan-control.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=ASUS Fan Control
Comment=Fan control and keyboard backlight for ASUS ROG G531GT
Exec=python3 $APP_DIR/fan-control.py
Icon=preferences-system
Terminal=false
Type=Application
Categories=System;Settings;
EOF
ok "Desktop launcher created"

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo ""
echo "  • Fan control service is running (GPU fan OFF, Quiet profile)"
echo "  • App: search 'ASUS Fan Control' in your app menu"
echo "  • Or run: python3 $APP_DIR/fan-control.py"
echo ""
