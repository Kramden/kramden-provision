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

        # Create vbox
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Create scrollable window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        check_snaps_row = Adw.ExpanderRow(title="Check Snaps")
        snaps_installed = self.utils.check_snaps(snap_packages)
        for snap in snaps_installed.keys():
            row = Adw.ActionRow(title=snap)
            check_snaps_row.add_row(row)
            if not snaps_installed[snap]:
                row.set_icon_name("emblem-important-symbolic")
                button = Gtk.Button(label='Fix')
                button.connect('clicked', self.on_fix_clicked, snap)
                row.add_suffix(button)
                check_snaps_row.set_expanded(True)
            else:
                row.set_icon_name("emblem-ok-symbolic")

        check_debs_row = Adw.ExpanderRow(title="Check System Packages")
        debs_installed = self.utils.check_debs(deb_packages)
        for deb in debs_installed.keys():
            row = Adw.ActionRow(title=deb)
            check_debs_row.add_row(row)
            if not debs_installed[deb]:
                row.set_icon_name("emblem-important-symbolic")
                button = Gtk.Button(label="Fix")
                button.connect('clicked', self.on_fix_clicked, deb)
                row.add_suffix(button)
                check_debs_row.set_expanded(True)
            else:
                row.set_icon_name("emblem-ok-symbolic")

        vbox.append(check_snaps_row)
        vbox.append(check_debs_row)
        scrolled_window.set_child(vbox)
        self.set_child(scrolled_window)

    def on_fix_clicked(self, button, package):
        print('on_fix_clicked: ' + package)
