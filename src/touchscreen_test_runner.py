#!/usr/bin/env python3
"""Standalone touchscreen test runner.

Run as a subprocess by the manual test page so a SIGSEGV inside GTK/GDK
touch event handling (reproducible after USB device unplug) cannot
take down the main provisioning app. Writes a single line to stdout:
"pass" or "fail", then exits.
"""

import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk


class TouchscreenTest(Gtk.ApplicationWindow):
    """Fullscreen white window with 8 touch targets that must all be tapped to pass."""

    TARGET_POSITIONS = [
        (0.08, 0.08),
        (0.92, 0.08),
        (0.08, 0.92),
        (0.92, 0.92),
        (0.30, 0.30),
        (0.70, 0.30),
        (0.30, 0.70),
        (0.70, 0.70),
    ]
    TARGET_SIZE = 60
    REPOSITION_DELAY_MS = 16

    def __init__(self, app, on_complete):
        super().__init__(application=app)
        self._on_complete = on_complete
        self._reposition_source_id = None
        self._finish_source_id = None
        self.set_decorated(False)

        css = Gtk.CssProvider()
        css.load_from_string(
            "window.touchscreen-test { background-color: white; }"
            ".touchscreen-instructions { color: #1f1f1f; font-size: 22px; "
            "font-weight: bold; }"
            ".touch-target { background: #4d4d4d; border-radius: 50%; "
            "min-width: 60px; min-height: 60px; border: none; padding: 0; }"
            ".touch-target.touched { background: #33cc33; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.add_css_class("touchscreen-test")

        self._fixed = Gtk.Fixed()
        self._fixed.set_hexpand(True)
        self._fixed.set_vexpand(True)

        overlay = Gtk.Overlay()
        overlay.set_child(self._fixed)
        self.set_child(overlay)

        instructions = Gtk.Label(
            label="Touch every spot with your finger until all spots are green to pass the test."
        )
        instructions.add_css_class("touchscreen-instructions")
        instructions.set_halign(Gtk.Align.CENTER)
        instructions.set_valign(Gtk.Align.START)
        instructions.set_margin_top(18)
        overlay.add_overlay(instructions)

        quit_btn = Gtk.Button(label="Quit")
        quit_btn.add_css_class("destructive-action")
        quit_btn.set_halign(Gtk.Align.END)
        quit_btn.set_valign(Gtk.Align.START)
        quit_btn.set_margin_top(12)
        quit_btn.set_margin_end(12)
        quit_btn.connect("clicked", self._on_quit)
        overlay.add_overlay(quit_btn)

        self._targets = []
        for i, (_fx, _fy) in enumerate(self.TARGET_POSITIONS):
            target = Gtk.Box()
            target.add_css_class("touch-target")
            target.set_size_request(self.TARGET_SIZE, self.TARGET_SIZE)
            self._fixed.put(target, 0, 0)
            self._targets.append(target)

        fixed_gesture = Gtk.GestureClick()
        fixed_gesture.set_touch_only(False)
        fixed_gesture.connect("pressed", self._on_fixed_pressed)
        self._fixed.add_controller(fixed_gesture)

        self._touched = [False] * len(self.TARGET_POSITIONS)

        self._fixed.connect("notify::width", self._on_layout_changed)
        self._fixed.connect("notify::height", self._on_layout_changed)
        self.connect("map", self._on_map)
        self.connect("close-request", self._on_close_request)

    def _on_map(self, widget):
        self.fullscreen()
        self._queue_reposition_targets()

    def _on_layout_changed(self, *args):
        self._queue_reposition_targets()

    def _queue_reposition_targets(self):
        if self._reposition_source_id is not None:
            return
        self._reposition_source_id = GLib.timeout_add(
            self.REPOSITION_DELAY_MS, self._reposition_targets
        )

    @staticmethod
    def _calculate_target_coordinates(width, height):
        if width <= 1 or height <= 1:
            return []
        half = TouchscreenTest.TARGET_SIZE // 2
        max_x = max(0, width - TouchscreenTest.TARGET_SIZE)
        max_y = max(0, height - TouchscreenTest.TARGET_SIZE)
        coordinates = []
        for fx, fy in TouchscreenTest.TARGET_POSITIONS:
            x = max(0, min(int(fx * width) - half, max_x))
            y = max(0, min(int(fy * height) - half, max_y))
            coordinates.append((x, y))
        return coordinates

    def _reposition_targets(self, *args):
        self._reposition_source_id = None
        width = self._fixed.get_width()
        height = self._fixed.get_height()
        coordinates = self._calculate_target_coordinates(width, height)
        if not coordinates:
            self._queue_reposition_targets()
            return False
        for i, (x, y) in enumerate(coordinates):
            self._fixed.move(self._targets[i], x, y)
        return False

    def _on_fixed_pressed(self, gesture, n_press, x, y):
        width = self._fixed.get_width()
        height = self._fixed.get_height()
        coordinates = self._calculate_target_coordinates(width, height)
        size = TouchscreenTest.TARGET_SIZE
        for i, (tx, ty) in enumerate(coordinates):
            if tx <= x < tx + size and ty <= y < ty + size:
                self._on_target_pressed(self._targets[i], i)
                return

    def _on_target_pressed(self, target, index):
        if self._touched[index]:
            return
        self._touched[index] = True
        target.add_css_class("touched")
        if all(self._touched) and self._finish_source_id is None:
            self._finish_source_id = GLib.timeout_add(300, self._finish_passed)

    def _finish_passed(self):
        self._finish_source_id = None
        self._on_complete(True)
        self.close()
        return False

    def _on_quit(self, button):
        self._on_complete(False)
        self.close()

    def _on_close_request(self, *args):
        if self._reposition_source_id is not None:
            GLib.source_remove(self._reposition_source_id)
            self._reposition_source_id = None
        if self._finish_source_id is not None:
            GLib.source_remove(self._finish_source_id)
            self._finish_source_id = None
        return False


class _App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.kramden.touchscreen-test")
        Adw.init()
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        self._result = "fail"

    def do_activate(self):
        win = TouchscreenTest(self, self._on_complete)
        win.present()

    def _on_complete(self, passed):
        self._result = "pass" if passed else "fail"
        self.quit()


def main():
    app = _App()
    app.run([])
    sys.stdout.write(app._result + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
