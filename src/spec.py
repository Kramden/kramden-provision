#!/usr/bin/env python3

import gi
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gdk, Gtk, Adw

import os
from specinfo import SpecInfo
from manualtest import ManualTest
from speccomplete import SpecComplete
from observable import ObservableProperty, StateObserver

class WizardWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Kramden - Spec")

        self.set_icon_name("kramden")
        self.set_default_size(800, 800)

        # Initialize the observable property for tracking state
        self.observable_property = ObservableProperty({"SpecInfo": False, "ManualTest": False})
        # Create and add an observer
        observer = StateObserver()
        self.observable_property.add_observer(observer)

        # Create Gtk.HeaderBar
        header_bar = Gtk.HeaderBar()
        header_bar_title = Gtk.Label(label="Kramden - Spec")
        header_bar.set_title_widget(header_bar_title)
        header_bar.set_show_title_buttons(True)

        # Navigation Buttons
        self.prev_button = Gtk.Button(label="Previous")
        self.prev_button.connect("clicked", self.on_prev_clicked)
        self.next_button = Gtk.Button(label="Next")
        self.next_button.connect("clicked", self.on_next_clicked)

        header_bar.pack_start(self.prev_button)
        header_bar.pack_end(self.next_button)

        self.set_titlebar(header_bar)

        # Create a page title widget
        self.title_widget = Gtk.Label(label="Spec")

        # Create a header
        header = Adw.HeaderBar()
        header.set_decoration_layout("") # Remove window controls
        header.set_title_widget(self.title_widget)

        # View Stack
        self.stack = Adw.ViewStack()
        self.page1 = SpecInfo()
        self.page2 = ManualTest()
        self.page3 = SpecComplete()

        self.page1.state = self.observable_property
        self.page2.state = self.observable_property
        self.page3.state = self.observable_property

        
        self.stack.add_named(self.page1, "page1")
        self.stack.add_named(self.page2, "page2")
        self.stack.add_named(self.page3, "page3")

        self.stack.set_vexpand(True)  # Ensure the stack expands vertically

        # Content Box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(header)
        content_box.append(self.stack)

        self.set_child(content_box)
        self.current_page = 0
        self.update_buttons()

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

        # Fake visible change to set state info
        self.page1.on_shown()

    def on_visible_page_changed(self, stack, params):
        print("on_visible_page_changed")
        current = stack.get_visible_child()
        self.title_widget.set_label(current.title)
        current.on_shown()

    def on_prev_clicked(self, button=None):
        if self.current_page > 0:
            self.current_page -= 1
            self.stack.set_visible_child_name(f"page{self.current_page + 1}")
            self.update_buttons()
            page = eval(f"self.page{self.current_page + 1}")
            if page.skip:
                print(f'on_prev_clicked: page{self.current_page - 1} skipped')
                self.on_prev_clicked()

    def on_next_clicked(self, button=None):
        if self.current_page < 3:
            self.current_page += 1
            self.stack.set_visible_child_name(f"page{self.current_page + 1}")
            self.update_buttons()
            page = eval(f"self.page{self.current_page + 1}")
            if page.skip:
                print(f'on_next_clicked: page{self.current_page + 1} skipped')
                self.on_next_clicked()
        else:
            self.complete()

    def update_buttons(self):
        self.prev_button.set_sensitive(self.current_page > 0)
        self.next_button.set_sensitive(self.current_page <= 3)
        if self.current_page == 3:
            self.next_button.set_label("Complete")
            self.next_button.add_css_class("button-next-last-page")
            state = self.observable_property.get_value()
            self.next_button.set_sensitive(all(state.values()))
        else:
            self.next_button.remove_css_class("button-next-last-page")
            self.next_button.set_label("Next")

        # Focus the next button
        self.next_button.grab_focus()

    def complete(self):
        print("Complete Clicked")
        self.page4.complete()

class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id='kramden-spec')
        Adw.init()

        # Set Adwaita dark theme preference using Adw.StyleManager
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def do_activate(self):
        window = WizardWindow(self)
        self.add_window(window)
        window.present()

app = Application()
app.run([])
