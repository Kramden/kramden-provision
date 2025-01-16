import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

class FinalTestComplete(Adw.Bin):
    def __init__(self):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        
        label = Gtk.Label(label="Final Test Complete!")
        self.set_child(label)
