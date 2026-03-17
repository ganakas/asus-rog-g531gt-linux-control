# ASUS ROG Strix G531GT — Linux Control

Fan control, keyboard backlight, and thermal management for the **ASUS ROG Strix G531GT** (Intel i7-9750H + NVIDIA GTX 1650) on Zorin OS / Ubuntu.

## Files

| File | Install path | Description |
|---|---|---|
| `fan-control.py` | `~/asus-fan-control/` | GTK4 + Adwaita GUI app |
| `asus-fan-control.sh` | `/usr/local/bin/` | Boot-time fan control + safety monitor |
| `asus-kbd-backlight` | `/usr/local/bin/` | Keyboard backlight via direct HID |
| `asus-fan-control.service` | `/etc/systemd/system/` | Systemd service |

## What it does

- **GPU fan OFF** at idle (ACPI ATK WMI call) with 90 °C safety re-enable
- **CPU fan** set to Quiet thermal profile (~3300–4300 RPM instead of 6900)
- **Keyboard backlight** — colour, effects (Static / Breathe / Rainbow / etc.), brightness 0–3, all without `asusd`
- **GTK4 app** — live temperature/RPM monitor, GPU fan toggle, profile selector, colour picker with live preview

## Install

```bash
# Copy scripts
sudo cp asus-fan-control.sh asus-kbd-backlight /usr/local/bin/
sudo chmod +x /usr/local/bin/asus-fan-control.sh /usr/local/bin/asus-kbd-backlight

# Enable service
sudo cp asus-fan-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asus-fan-control

# Run the app
python3 fan-control.py
```

## Requirements

- `acpi_call` kernel module (`sudo modprobe acpi_call`)
- `nvidia-smi` (for GPU temp)
- `lm-sensors`
- Python 3, GTK 4, libadwaita (`python3-gi`, `gir1.2-adw-1`)
