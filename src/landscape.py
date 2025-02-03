import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

class Landscape(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.title = "Landscape Registration"
        self.passed = True
        
        label = Gtk.Label(label="Landscape Registration")
        self.set_child(label)

    def on_shown(self):
        pass
