#!/bin/bash
# ASUS ROG G531GT - Fan control via ACPI ATK WMI
# GPU fan: DEVS 0x00110023 (EC0: 0xD8 ctrl, 0xD9 hi, 0xDA lo)
# Thermal profile: Quiet (2) = lower CPU fan noise
#
# IMPORTANT: Do NOT set CPU fan custom mode (0x00110022) — the EC
# interprets speed=0 as "run at max" for safety. CPU fan is managed
# by the EC thermal curve. Use Quiet profile for lower RPM.

ACPI_CALL=/proc/acpi/call
GPU_OFF="{0x23,0x00,0x11,0x00,0x00,0x00,0x00,0x00}"
THERMAL_POLICY=/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy
SAFETY_TEMP=90

modprobe acpi_call 2>/dev/null

# Set Quiet thermal profile (lowest CPU fan noise)
echo 2 > "$THERMAL_POLICY" 2>/dev/null

# Wait for EC to process profile change
sleep 2

# Turn off GPU fan
echo "\_SB.ATKD.WMNB 0x00 0x53564544 $GPU_OFF" > "$ACPI_CALL"

# Initialise keyboard backlight (Aura static mode + max brightness)
# Must be done directly via HID to avoid asusd resetting fans
asus-kbd-backlight 3 2>/dev/null && logger "asus-fan: keyboard backlight ON"

logger "asus-fan: GPU fan OFF, thermal=Quiet"

# Safety monitor loop
while true; do
    sleep 30
    GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo 0)
    GPU_FAN=$(cat /sys/class/hwmon/hwmon5/fan2_input 2>/dev/null || echo 0)

    if [ "$GPU_TEMP" -ge "$SAFETY_TEMP" ] && [ "$GPU_FAN" -eq 0 ]; then
        # Re-enable GPU fan via profile reset, then set back to Quiet
        echo 0 > "$THERMAL_POLICY" 2>/dev/null
        sleep 2
        echo 2 > "$THERMAL_POLICY" 2>/dev/null
        logger "asus-fan: GPU ${GPU_TEMP}°C >= ${SAFETY_TEMP}°C — auto enabled"
    elif [ "$GPU_TEMP" -lt $((SAFETY_TEMP - 10)) ] && [ "$GPU_FAN" -gt 0 ]; then
        echo "\_SB.ATKD.WMNB 0x00 0x53564544 $GPU_OFF" > "$ACPI_CALL"
        logger "asus-fan: GPU ${GPU_TEMP}°C < $((SAFETY_TEMP - 10))°C — fan OFF"
    fi
done
