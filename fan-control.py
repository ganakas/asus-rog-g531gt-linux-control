#!/usr/bin/env python3
"""ASUS ROG G531GT Fan Monitor & Control — GTK4 + Adwaita app.

Runs as regular user. Uses sudo (NOPASSWD) for privileged ACPI/sysfs writes.
Reads from sysfs/nvidia-smi don't need root.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

import subprocess
import threading
from gi.repository import Gtk, Adw, GLib, Gdk

ACPI_CALL = '/proc/acpi/call'
THERMAL_POLICY = '/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy'
FAN1_INPUT = '/sys/class/hwmon/hwmon5/fan1_input'
FAN2_INPUT = '/sys/class/hwmon/hwmon5/fan2_input'
CPU_TEMP = '/sys/class/thermal/thermal_zone0/temp'

GPU_OFF_CMD = r'\_SB.ATKD.WMNB 0x00 0x53564544 {0x23,0x00,0x11,0x00,0x00,0x00,0x00,0x00}'

KBD_BACKLIGHT = '/sys/class/leds/asus::kbd_backlight/brightness'
KBD_MAX_BRIGHTNESS = '/sys/class/leds/asus::kbd_backlight/max_brightness'
SCREEN_BACKLIGHT = '/sys/class/backlight/intel_backlight/brightness'
SCREEN_MAX_BRIGHTNESS = '/sys/class/backlight/intel_backlight/max_brightness'

# Aura effects: (display name, mode number)
EFFECTS = [
    ('Static',        0),
    ('Breathe',       1),
    ('Rainbow Cycle', 2),
    ('Rainbow Wave',  3),
    ('Stars',         4),
    ('Rain',          5),
    ('Ripple',        8),
    ('Pulse',         10),
    ('Comet',         11),
    ('Flash',         12),
]
SPEEDS = ['low', 'med', 'high']


def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except (OSError, IOError):
        return None


def sudo_write(path, value):
    """Write to a privileged file via sudo tee."""
    try:
        subprocess.run(
            ['sudo', 'tee', path],
            input=str(value), capture_output=True, text=True, timeout=5
        )
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def acpi_call(cmd):
    """Send ACPI call via sudo."""
    try:
        subprocess.run(
            ['sudo', 'bash', '-c', f"echo '{cmd}' > {ACPI_CALL}"],
            capture_output=True, timeout=5
        )
        return read_file(ACPI_CALL)
    except (subprocess.TimeoutExpired, OSError):
        return None


def get_gpu_temp():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        return int(result.stdout.strip()) if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None


def get_cpu_temp():
    val = read_file(CPU_TEMP)
    return int(val) // 1000 if val else None


def get_fan_rpm(path):
    val = read_file(path)
    return int(val) if val else 0


def get_thermal_profile():
    val = read_file(THERMAL_POLICY)
    return int(val) if val is not None else 0


def set_thermal_profile(profile_id):
    return sudo_write(THERMAL_POLICY, profile_id)


def gpu_fan_off():
    return acpi_call(GPU_OFF_CMD)


def get_kbd_brightness():
    val = read_file(KBD_BACKLIGHT)
    return int(val) if val is not None else 0


def get_kbd_max():
    val = read_file(KBD_MAX_BRIGHTNESS)
    return int(val) if val is not None else 3


def set_kbd_backlight(level, mode=0, color='ffffff', speed='med'):
    """Set keyboard backlight via direct HID + sysfs (bypasses asusd)."""
    try:
        subprocess.run(
            ['sudo', 'asus-kbd-backlight', str(int(level)),
             '--mode', str(mode), '--color', color, '--speed', speed],
            capture_output=True, timeout=5
        )
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def get_screen_brightness():
    val = read_file(SCREEN_BACKLIGHT)
    return int(val) if val is not None else 0


def get_screen_max():
    val = read_file(SCREEN_MAX_BRIGHTNESS)
    return int(val) if val is not None else 100


def set_screen_brightness(level):
    return sudo_write(SCREEN_BACKLIGHT, int(level))


class FanControlApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.asus.fancontrol')
        self.connect('activate', self.on_activate)
        self._updating_profile = False
        self._kbd_effect = 0       # Static
        self._kbd_color = 'ffffff'
        self._kbd_speed = 'med'
        self._kbd_color_timeout = None

    def on_activate(self, app):
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_title('ASUS Fan Control')
        self.win.set_default_size(420, 580)
        self.win.set_resizable(True)

        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)

        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_start(0)
        content.set_margin_end(0)

        # --- Temperatures group ---
        temp_group = Adw.PreferencesGroup(title='Temperatures')
        temp_group.set_margin_start(12)
        temp_group.set_margin_end(12)
        temp_group.set_margin_top(12)

        self.cpu_temp_row = Adw.ActionRow(title='CPU')
        self.cpu_temp_label = Gtk.Label(label='—')
        self.cpu_temp_label.add_css_class('title-3')
        self.cpu_temp_row.add_suffix(self.cpu_temp_label)
        temp_group.add(self.cpu_temp_row)

        self.gpu_temp_row = Adw.ActionRow(title='GPU')
        self.gpu_temp_label = Gtk.Label(label='—')
        self.gpu_temp_label.add_css_class('title-3')
        self.gpu_temp_row.add_suffix(self.gpu_temp_label)
        temp_group.add(self.gpu_temp_row)

        content.append(temp_group)

        # --- Fans group ---
        fan_group = Adw.PreferencesGroup(title='Fans')
        fan_group.set_margin_start(12)
        fan_group.set_margin_end(12)
        fan_group.set_margin_top(12)

        self.cpu_fan_row = Adw.ActionRow(title='CPU Fan')
        self.cpu_fan_label = Gtk.Label(label='—')
        self.cpu_fan_label.add_css_class('title-3')
        self.cpu_fan_row.add_suffix(self.cpu_fan_label)
        fan_group.add(self.cpu_fan_row)

        self.gpu_fan_row = Adw.ActionRow(title='GPU Fan')
        self.gpu_fan_label = Gtk.Label(label='—')
        self.gpu_fan_label.add_css_class('title-3')
        self.gpu_fan_row.add_suffix(self.gpu_fan_label)

        # GPU fan toggle
        self.gpu_fan_switch = Gtk.Switch()
        self.gpu_fan_switch.set_valign(Gtk.Align.CENTER)
        self.gpu_fan_switch.set_tooltip_text('GPU fan OFF when disabled')
        self.gpu_fan_switch.connect('state-set', self.on_gpu_fan_toggle)
        self.gpu_fan_row.add_suffix(self.gpu_fan_switch)

        fan_group.add(self.gpu_fan_row)
        content.append(fan_group)

        # --- Profile group ---
        profile_group = Adw.PreferencesGroup(title='Thermal Profile')
        profile_group.set_margin_start(12)
        profile_group.set_margin_end(12)
        profile_group.set_margin_top(12)
        profile_group.set_margin_bottom(12)

        self.profile_row = Adw.ActionRow(title='Profile')
        self.profile_row.set_subtitle('Controls CPU fan curve aggressiveness')

        # Profile dropdown
        profile_list = Gtk.StringList.new(['Quiet', 'Balanced', 'Performance'])
        self.profile_dropdown = Gtk.DropDown(model=profile_list)
        self.profile_dropdown.set_valign(Gtk.Align.CENTER)
        self.profile_dropdown.connect('notify::selected', self.on_profile_changed)
        self.profile_row.add_suffix(self.profile_dropdown)

        profile_group.add(self.profile_row)
        content.append(profile_group)

        # --- Backlight group ---
        bl_group = Adw.PreferencesGroup(title='Backlight')
        bl_group.set_margin_start(12)
        bl_group.set_margin_end(12)
        bl_group.set_margin_top(12)
        bl_group.set_margin_bottom(12)

        # Keyboard backlight
        self.kbd_row = Adw.ActionRow(title='Keyboard')
        self.kbd_row.set_subtitle('0 = off, 3 = max')
        kbd_max = get_kbd_max()
        self.kbd_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, kbd_max, 1)
        self.kbd_scale.set_draw_value(True)
        self.kbd_scale.set_value_pos(Gtk.PositionType.LEFT)
        self.kbd_scale.set_size_request(180, -1)
        self.kbd_scale.set_valign(Gtk.Align.CENTER)
        for i in range(kbd_max + 1):
            self.kbd_scale.add_mark(i, Gtk.PositionType.BOTTOM, None)
        self.kbd_scale.set_value(get_kbd_brightness() if get_kbd_brightness() else 3)
        self.kbd_scale.connect('value-changed', self.on_kbd_changed)
        self.kbd_row.add_suffix(self.kbd_scale)
        bl_group.add(self.kbd_row)

        # Keyboard effect
        self.kbd_effect_row = Adw.ActionRow(title='Effect')
        effect_names = Gtk.StringList.new([e[0] for e in EFFECTS])
        self.kbd_effect_dd = Gtk.DropDown(model=effect_names)
        self.kbd_effect_dd.set_valign(Gtk.Align.CENTER)
        self.kbd_effect_dd.connect('notify::selected', self.on_kbd_effect_changed)
        self.kbd_effect_row.add_suffix(self.kbd_effect_dd)
        bl_group.add(self.kbd_effect_row)

        # Keyboard colour — inline live picker (expander)
        self.kbd_color_expander = Adw.ExpanderRow(title='Colour')
        self.kbd_color_expander.set_subtitle('Expand — changes apply live')

        # Back button (hidden until editor mode is opened)
        self.kbd_color_back_btn = Gtk.Button(label='← Back to palette')
        self.kbd_color_back_btn.add_css_class('flat')
        self.kbd_color_back_btn.set_halign(Gtk.Align.START)
        self.kbd_color_back_btn.set_margin_start(8)
        self.kbd_color_back_btn.set_margin_top(4)
        self.kbd_color_back_btn.set_visible(False)
        self.kbd_color_back_btn.connect('clicked', self.on_kbd_color_back)

        self.kbd_color_chooser = Gtk.ColorChooserWidget()
        self.kbd_color_chooser.set_use_alpha(False)
        self.kbd_color_chooser.set_margin_start(8)
        self.kbd_color_chooser.set_margin_end(8)
        self.kbd_color_chooser.set_margin_bottom(8)
        init_rgba = Gdk.RGBA()
        init_rgba.red = 1.0; init_rgba.green = 1.0; init_rgba.blue = 1.0; init_rgba.alpha = 1.0
        self.kbd_color_chooser.set_rgba(init_rgba)
        self.kbd_color_chooser.connect('notify::rgba', self.on_kbd_color_changed)
        self.kbd_color_chooser.connect('notify::show-editor', self.on_kbd_editor_toggled)

        color_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        color_inner.append(self.kbd_color_back_btn)
        color_inner.append(self.kbd_color_chooser)
        self.kbd_color_expander.add_row(color_inner)
        bl_group.add(self.kbd_color_expander)

        # Keyboard speed
        self.kbd_speed_row = Adw.ActionRow(title='Speed')
        self.kbd_speed_row.set_subtitle('For animated effects')
        speed_list = Gtk.StringList.new(['Low', 'Medium', 'High'])
        self.kbd_speed_dd = Gtk.DropDown(model=speed_list)
        self.kbd_speed_dd.set_selected(1)  # Medium default
        self.kbd_speed_dd.set_valign(Gtk.Align.CENTER)
        self.kbd_speed_dd.connect('notify::selected', self.on_kbd_speed_changed)
        self.kbd_speed_row.add_suffix(self.kbd_speed_dd)
        bl_group.add(self.kbd_speed_row)

        # Screen brightness
        self.screen_row = Adw.ActionRow(title='Screen')
        scr_max = get_screen_max()
        self.screen_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, scr_max, max(1, scr_max // 100))
        self.screen_scale.set_draw_value(False)
        self.screen_scale.set_size_request(180, -1)
        self.screen_scale.set_valign(Gtk.Align.CENTER)
        self.screen_scale.set_value(get_screen_brightness())
        self.screen_scale.connect('value-changed', self.on_screen_changed)
        self.screen_row.add_suffix(self.screen_scale)
        bl_group.add(self.screen_row)

        content.append(bl_group)

        scroll.set_child(content)
        main_box.append(scroll)

        self.win.set_content(main_box)
        self.win.present()

        # Initial state read
        self._sync_profile_dropdown()
        self._sync_gpu_switch()

        # Start periodic updates (2 seconds)
        GLib.timeout_add_seconds(2, self._update_readings)
        self._update_readings()

    def _sync_profile_dropdown(self):
        """Sync dropdown to current thermal policy."""
        self._updating_profile = True
        current = get_thermal_profile()
        # Dropdown order: 0=Quiet, 1=Balanced, 2=Performance
        dropdown_map = {2: 0, 0: 1, 1: 2}  # policy -> dropdown index
        self.profile_dropdown.set_selected(dropdown_map.get(current, 1))
        self._updating_profile = False

    def _sync_gpu_switch(self):
        """Sync GPU fan switch to current state."""
        gpu_rpm = get_fan_rpm(FAN2_INPUT)
        # Switch ON = fan running (auto), OFF = fan stopped
        self.gpu_fan_switch.set_active(gpu_rpm > 0)

    def _update_readings(self):
        """Update all sensor readings."""
        cpu_t = get_cpu_temp()
        gpu_t = get_gpu_temp()
        cpu_rpm = get_fan_rpm(FAN1_INPUT)
        gpu_rpm = get_fan_rpm(FAN2_INPUT)

        self.cpu_temp_label.set_text(f'{cpu_t}°C' if cpu_t is not None else '—')
        self.gpu_temp_label.set_text(f'{gpu_t}°C' if gpu_t is not None else '—')
        self.cpu_fan_label.set_text(f'{cpu_rpm} RPM')
        self.gpu_fan_label.set_text(f'{gpu_rpm} RPM')

        # Color temperature labels
        if cpu_t is not None:
            self._set_temp_style(self.cpu_temp_label, cpu_t)
        if gpu_t is not None:
            self._set_temp_style(self.gpu_temp_label, gpu_t)

        # Sync GPU switch without triggering callback
        self.gpu_fan_switch.handler_block_by_func(self.on_gpu_fan_toggle)
        self.gpu_fan_switch.set_active(gpu_rpm > 0)
        self.gpu_fan_switch.handler_unblock_by_func(self.on_gpu_fan_toggle)

        return True  # keep running

    def _set_temp_style(self, label, temp):
        for cls in ['success', 'warning', 'error']:
            label.remove_css_class(cls)
        if temp >= 85:
            label.add_css_class('error')
        elif temp >= 70:
            label.add_css_class('warning')
        else:
            label.add_css_class('success')

    def on_gpu_fan_toggle(self, switch, state):
        """Handle GPU fan toggle."""
        def _do_toggle():
            if not state:
                # Turn OFF
                gpu_fan_off()
            else:
                # Turn ON (reset to auto by cycling profile)
                current = get_thermal_profile()
                set_thermal_profile(0)
                GLib.usleep(500000)
                set_thermal_profile(current)
            GLib.idle_add(self._update_readings)
        threading.Thread(target=_do_toggle, daemon=True).start()
        return False

    def on_profile_changed(self, dropdown, _param):
        """Handle thermal profile change."""
        if self._updating_profile:
            return
        # Dropdown: 0=Quiet, 1=Balanced, 2=Performance
        dropdown_to_policy = {0: 2, 1: 0, 2: 1}
        idx = dropdown.get_selected()
        policy = dropdown_to_policy.get(idx, 0)

        def _do_profile():
            set_thermal_profile(policy)
            GLib.usleep(2000000)
            # Re-apply GPU fan off if it was off
            gpu_rpm = get_fan_rpm(FAN2_INPUT)
            if gpu_rpm > 0:
                # Profile change turned it on; check if user wants it off
                GLib.idle_add(self._check_reapply_gpu_off)
            GLib.idle_add(self._update_readings)
        threading.Thread(target=_do_profile, daemon=True).start()

    def _check_reapply_gpu_off(self):
        """After profile change, re-disable GPU fan if switch is off."""
        if not self.gpu_fan_switch.get_active():
            threading.Thread(target=gpu_fan_off, daemon=True).start()

    def on_kbd_changed(self, scale):
        """Handle keyboard backlight slider."""
        self._apply_kbd_settings()

    def on_kbd_effect_changed(self, dropdown, _param):
        """Handle keyboard effect change."""
        idx = dropdown.get_selected()
        self._kbd_effect = EFFECTS[idx][1]
        self._apply_kbd_settings()

    def on_kbd_editor_toggled(self, chooser, _param):
        """Show/hide back button when entering/leaving custom editor."""
        self.kbd_color_back_btn.set_visible(
            chooser.get_property('show-editor'))

    def on_kbd_color_back(self, _btn):
        """Return from custom editor to colour palette."""
        self.kbd_color_chooser.set_property('show-editor', False)

    def on_kbd_color_changed(self, chooser, _param=None):
        """Handle keyboard color — live update with debounce."""
        rgba = chooser.get_rgba()
        r = int(rgba.red * 255)
        g = int(rgba.green * 255)
        b = int(rgba.blue * 255)
        self._kbd_color = f'{r:02x}{g:02x}{b:02x}'
        if self._kbd_color_timeout:
            GLib.source_remove(self._kbd_color_timeout)
        self._kbd_color_timeout = GLib.timeout_add(150, self._apply_kbd_debounced)

    def _apply_kbd_debounced(self):
        self._kbd_color_timeout = None
        self._apply_kbd_settings()
        return False

    def on_kbd_speed_changed(self, dropdown, _param):
        """Handle animation speed change."""
        self._kbd_speed = SPEEDS[dropdown.get_selected()]
        self._apply_kbd_settings()

    def _apply_kbd_settings(self):
        val = int(self.kbd_scale.get_value())
        threading.Thread(
            target=set_kbd_backlight,
            args=(val, self._kbd_effect, self._kbd_color, self._kbd_speed),
            daemon=True
        ).start()

    def on_screen_changed(self, scale):
        """Handle screen brightness slider."""
        val = int(scale.get_value())
        threading.Thread(target=set_screen_brightness, args=(val,), daemon=True).start()


def main():
    app = FanControlApp()
    return app.run(None)


if __name__ == '__main__':
    raise SystemExit(main())
