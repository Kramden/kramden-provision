#!/usr/bin/env python3
"""Standalone fullscreen "click the affected screen section(s)" picker.

Run as a subprocess by the manual test page (see _build_section_picker in
manualtest_v3.py) so the tech can point directly at the physical screen --
which is split into a 2x3 grid of sections -- instead of picking from a
small button grid embedded in the app. Prints the selected section
name(s), comma-separated (may be empty), on a single line to stdout, then
exits. Kept standalone (no import of manualtest_v3.py) to match
touchscreen_test_runner.py; SECTIONS below must be kept in sync with
SCREEN_SECTIONS there.
"""

import argparse
import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gtk

SECTIONS = [
    "Upper Left",
    "Upper Middle",
    "Upper Right",
    "Lower Left",
    "Lower Middle",
    "Lower Right",
]


class SectionPicker(Gtk.ApplicationWindow):
    """Fullscreen plain-white window split into a bordered 2x3 grid. Clicking
    a cell toggles it as selected (border/text turn green) and a Submit
    button in the top right finishes the picker, reporting every currently
    selected section."""

    def __init__(self, app, on_complete, heading, select_all_label, initial_selected):
        super().__init__(application=app)
        self._on_complete = on_complete
        self.set_decorated(False)

        css = Gtk.CssProvider()
        css.load_from_string(
            "window.section-picker { background-color: white; }"
            ".section-picker-heading { color: #1f1f1f; font-size: 20px; "
            "font-weight: bold; }"
            ".section-cell { background-color: white; border: 3px solid "
            "#808080; border-radius: 0; color: #1f1f1f; font-size: 22px; "
            "font-weight: bold; }"
            ".section-cell.selected { border: 5px solid #3fe35a; "
            "color: #3fe35a; background-color: rgba(63, 227, 90, 0.12); }"
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self.add_css_class("section-picker")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_top(12)
        top_bar.set_margin_bottom(6)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)

        heading_label = Gtk.Label(label=heading)
        heading_label.add_css_class("section-picker-heading")
        heading_label.set_hexpand(True)
        heading_label.set_halign(Gtk.Align.START)
        heading_label.set_wrap(True)
        top_bar.append(heading_label)

        if select_all_label:
            select_all_button = Gtk.Button(label=select_all_label)
            select_all_button.set_valign(Gtk.Align.CENTER)
            select_all_button.connect("clicked", self._on_select_all)
            top_bar.append(select_all_button)

        submit_button = Gtk.Button(label="Submit")
        submit_button.add_css_class("suggested-action")
        submit_button.set_valign(Gtk.Align.CENTER)
        submit_button.connect("clicked", self._on_submit)
        top_bar.append(submit_button)

        outer.append(top_bar)

        grid = Gtk.Grid()
        grid.set_hexpand(True)
        grid.set_vexpand(True)
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_bottom(12)

        self._buttons = {}
        for index, section in enumerate(SECTIONS):
            row, col = divmod(index, 3)
            button = Gtk.ToggleButton(label=section)
            button.add_css_class("section-cell")
            button.set_hexpand(True)
            button.set_vexpand(True)
            if section in initial_selected:
                button.set_active(True)
                button.add_css_class("selected")
            button.connect("toggled", self._on_section_toggled, section)
            grid.attach(button, col, row, 1, 1)
            self._buttons[section] = button

        outer.append(grid)
        self.set_child(outer)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.connect("map", self._on_map)

    def _on_map(self, widget):
        self.fullscreen()

    def _on_section_toggled(self, button, section):
        if button.get_active():
            button.add_css_class("selected")
        else:
            button.remove_css_class("selected")

    def _on_select_all(self, button):
        for cell_button in self._buttons.values():
            cell_button.set_active(True)

    def _selected_sections(self):
        return [s for s in SECTIONS if self._buttons[s].get_active()]

    def _on_submit(self, button):
        self._finish()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._finish()
            return True
        return False

    def _finish(self):
        self._on_complete(self._selected_sections())
        self.close()


class _App(Adw.Application):
    def __init__(self, heading, select_all_label, initial_selected):
        super().__init__(application_id="org.kramden.section-picker")
        Adw.init()
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
        self._heading = heading
        self._select_all_label = select_all_label
        self._initial_selected = initial_selected
        self._result = []

    def do_activate(self):
        win = SectionPicker(
            self,
            self._on_complete,
            self._heading,
            self._select_all_label,
            self._initial_selected,
        )
        win.present()

    def _on_complete(self, selected):
        self._result = selected
        self.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--heading", default="Click every affected section, then press Submit."
    )
    parser.add_argument("--select-all-label", default="")
    parser.add_argument("--initial", default="")
    args = parser.parse_args()

    initial_selected = {s.strip() for s in args.initial.split(",") if s.strip()}

    app = _App(args.heading, args.select_all_label, initial_selected)
    app.run([])
    sys.stdout.write(",".join(app._result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
