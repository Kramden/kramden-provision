#!/usr/bin/env python3

import gi
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gdk, Gtk, Adw

import os
from sysinfo import SysInfo
from guide import KramdenGuide
from observable import ObservableProperty, StateObserver

class WizardWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Kramden - Guide")

        self.set_default_size(800, 800)
        self.connect('close-request', self.on_close)

        # Initialize the observable property for tracking state
        self.observable_property = ObservableProperty({"SysInfo": True})
        # Create and add an observer
        observer = StateObserver()
        self.observable_property.add_observer(observer)

        # Create Gtk.HeaderBar
        header_bar = Gtk.HeaderBar()
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_bar.set_title_widget(header_box)

        # Navigation Buttons
        self.sysinfo_button = Gtk.Button(label="Device Information")
        self.sysinfo_button.connect("clicked", self.on_sysinfo_clicked)
        self.guide_button = Gtk.Button(label="Kramden Guide")
        self.guide_button.connect("clicked", self.on_guide_clicked)

        header_box.append(self.guide_button)
        header_box.append(self.sysinfo_button)

        self.set_titlebar(header_bar)

        # Create a page title widget
        self.title_widget = Gtk.Label(label="OS Load")

        # View Stack
        self.stack = Adw.ViewStack()
        self.page1 = KramdenGuide()
        self.page1.state = self.observable_property
        self.page2 = SysInfo()
        self.page2.state = self.observable_property

        self.stack.add_named(self.page1, "page1")
        self.stack.add_named(self.page2, "page2")
        self.stack.set_vexpand(True)  # Ensure the stack expands vertically

        # Create footer
        self.footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.footer.set_hexpand(True)  # Ensure the footer expands horizontally
        image_path = os.path.dirname(os.path.realpath(__file__)) + "/getlearngive.png"
        picture = Gtk.Picture.new_for_filename(image_path)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        picture.set_size_request(800, 0)
        self.footer.append(picture)
        self.footer.set_visible(False) # Hide footer by default

        # Content Box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(self.stack)
        content_box.append(self.footer)

        self.set_child(content_box)

        self.page1.on_shown()

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(os.path.dirname(os.path.realpath(__file__)) + '/css/style.css')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Set title_widget after page was set
        self.stack.connect("notify::visible-child", self.on_visible_page_changed)
        self.title_widget.set_label(self.stack.get_visible_child().title)

    def on_visible_page_changed(self, stack, params):
        print("on_visible_page_changed")
        current = stack.get_visible_child()
        self.title_widget.set_label(current.title)
        current.on_shown()

    def on_guide_clicked(self, button):
        self.footer.set_visible(False)
        self.stack.set_visible_child_name(f"page1")
        self.guide_button.set_sensitive(False)
        self.sysinfo_button.set_sensitive(True)

    def on_sysinfo_clicked(self, button):
        self.footer.set_visible(True)
        self.stack.set_visible_child_name(f"page2")
        self.guide_button.set_sensitive(True)
        self.sysinfo_button.set_sensitive(False)

    def on_close(self, widget, arg=None):
        print("DeviceInfo: on_close")
        # Create file so we know we've launched before
        viewed_path = os.path.join(os.path.expanduser('~'), ".config", "kramden-intro-done")
        open(viewed_path, "w").close()

class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id='org.kramden.DeviceInfo')
        Adw.init()

        # Set Adwaita dark theme preference using Adw.StyleManager
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        window = WizardWindow(self)
        self.add_window(window)
        window.present()

# Run the application
if __name__ == "__main__":

    if os.getlogin() in ['ubuntu', 'osload', 'finaltest']:
        quit()

    app = Application()
    app.run([])
