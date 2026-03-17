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
git clone https://github.com/Ganakas/asus-rog-g531gt-linux-control.git
cd asus-rog-g531gt-linux-control
bash install.sh
```

Or download the assets from the [latest release](https://github.com/Ganakas/asus-rog-g531gt-linux-control/releases/latest), extract and run `bash install.sh`.

To uninstall:
```bash
bash uninstall.sh
```

## Requirements

- `acpi_call` kernel module (`sudo modprobe acpi_call`)
- `nvidia-smi` (for GPU temp)
- `lm-sensors`
- Python 3, GTK 4, libadwaita (`python3-gi`, `gir1.2-adw-1`)
