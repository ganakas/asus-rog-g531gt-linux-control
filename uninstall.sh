#!/bin/bash
# ASUS ROG Strix G531GT — Linux Control
# Uninstaller

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
step() { echo -e "\n${BOLD}$1${NC}"; }

echo -e "${BOLD}\n  Uninstalling ASUS ROG G531GT — Linux Control...\n${NC}"

step "Stopping service..."
sudo systemctl disable --now asus-fan-control 2>/dev/null || true
sudo rm -f /etc/systemd/system/asus-fan-control.service
sudo systemctl daemon-reload
ok "Service removed"

step "Removing scripts..."
sudo rm -f /usr/local/bin/asus-fan-control.sh
sudo rm -f /usr/local/bin/asus-kbd-backlight
ok "Scripts removed"

step "Removing app..."
rm -rf "$HOME/.local/share/asus-fan-control"
rm -f "$HOME/.local/share/applications/asus-fan-control.desktop"
ok "App removed"

echo -e "\n${GREEN}${BOLD}  Done. All files removed.${NC}\n"
