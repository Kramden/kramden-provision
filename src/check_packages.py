import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
from utils import Utils
from constants import snap_packages, deb_packages

class CheckPackages(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.utils = Utils()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Check Software"
        # Used to keep references to the Adw.ActionRow for each snap
        self.known_snap_rows = {}
        # Used to keep references to the Adw.ActionRow for each deb
        self.known_deb_rows = {}

        # Create vbox
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create scrollable window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.check_snaps_row = Adw.ExpanderRow(title="Check Snaps")
        self.check_debs_row = Adw.ExpanderRow(title="Check System Packages")

        vbox.append(self.check_snaps_row)
        vbox.append(self.check_debs_row)
        scrolled_window.set_child(vbox)
        self.set_child(scrolled_window)

    def on_fix_clicked(self, button, package):
        print('on_fix_clicked: ' + package)

    # on_shown is called when the page is shown in the stack
    def on_shown(self):
        passed = True
        snaps_installed = self.utils.check_snaps(snap_packages)
        for snap in snaps_installed.keys():
            # If we have an ActionRow already, remove it
            if snap in self.known_snap_rows.keys():
                self.check_snaps_row.remove(self.known_snap_rows[snap])
                del self.known_snap_rows[snap]

            row = Adw.ActionRow(title=snap)
            # Keep track of ActionRows to prevent duplication
            self.known_snap_rows[snap] = row
            self.check_snaps_row.add_row(row)

            # If not installed flag
            if not snaps_installed[snap]:
                row.set_icon_name("emblem-important-symbolic")
                row.add_css_class("text-error")
                # FIXME: Disable fix button until implemented
                # button = Gtk.Button(label='Fix')
                # button.connect('clicked', self.on_fix_clicked, snap)
                # row.add_suffix(button)
                self.check_snaps_row.set_expanded(True)
                passed = False
            else:
                row.set_icon_name("emblem-ok-symbolic")
                if row.has_css_class("text-error"):
                    row.remove_css_class("text-error")

        debs_installed = self.utils.check_debs(deb_packages)
        for deb in debs_installed.keys():
            # If we have an ActionRow already, remove it
            if deb in self.known_deb_rows.keys():
                self.check_debs_row.remove(self.known_deb_rows[deb])
                del self.known_deb_rows[deb]

            row = Adw.ActionRow(title=deb)
            # Keep track of ActionRows to prevent duplication
            self.known_deb_rows[deb] = row
            self.check_debs_row.add_row(row)

            # If not installed flag
            if not debs_installed[deb]:
                row.set_icon_name("emblem-important-symbolic")
                row.add_css_class("text-error")
                # FIXME: Disable fix button until implemented
                # button = Gtk.Button(label="Fix")
                # button.connect('clicked', self.on_fix_clicked, deb)
                # row.add_suffix(button)
                self.check_debs_row.set_expanded(True)
                passed = False
            else:
                row.set_icon_name("emblem-ok-symbolic")
                if row.has_css_class("text-error"):
                    row.remove_css_class("text-error")

        state = self.state.get_value()
        state['CheckPackages'] = passed
        print("check_packages:on_shown " + str(self.state.get_value()))
