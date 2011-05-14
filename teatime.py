#!/usr/bin/env python

import time
import json
import gettext

import os.path

from gi.repository import Unity, GObject, Gtk, Notify, Gdk, Pango

gettext.install("teatime")

from xdg.BaseDirectory import xdg_data_home

DATA = os.path.expanduser("~/workspace/teatime/")

if not os.path.exists(DATA):
    DATA = "/usr/share/teatime/"

class Notification(Notify.Notification):
    def __init__(self):
        Notify.Notification.__init__(self)
        self.set_urgency(Notify.Urgency.LOW)
   
    def set_info(self, timer):
        elapsed = time.time() - timer.end
        
        if elapsed < 20:
            body = "finished just now"
        elif elapsed < 60:
            body = "finished %s seconds ago" % time.strftime("%S", time.localtime(elapsed))
        else:
            body = "finished %s minutes ago" % time.strftime("%M:%S", time.localtime(elapsed))
            
        self.update("%s is ready" % timer.obj["name"], body, None)

class Timer:
    def __init__(self, obj):
        self.obj = obj
        self.running = False
        self.begin = None
        self.end = None
    
    def start(self):
        self.running = True
        self.begin = time.time()
        self.end = self.begin + self.obj["duration"]
    
    def get_progress(self):
        t = time.time()
        progress = (t - self.begin) / self.obj["duration"]
        
        self.running = progress < 1
        
        return progress

class TreeView:
    def __init__(self, obj, model):
        self._obj = obj
        
        self._model = model
        
        self._obj.connect("key-press-event", self._on_key_press)
        
        transl = (("name", _("Name")), ("duration", _("Duration")))

        for key, title in transl:
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            cell.set_property("editable", True)
            cell.connect('edited', self._edited_cb, key)
        
            col = Gtk.TreeViewColumn(title, cell)
            col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            col.set_min_width(100)
            col.set_fixed_width(200)
            col.set_cell_data_func(cell, self._data_func, key)
            self._obj.append_column(col)
    
    def _on_key_press(self, caller, ev):
        key = Gdk.keyval_name(ev.keyval)

        if key == "Delete":
            model, paths = self._obj.get_selection().get_selected_rows()
            paths = [model.get_iter(p) for p in paths]
    
            model.remove(paths[0])
    
    def add_addline(self):
        self._model.append({"name": _("New Entry"), "duration":0})
    
    def _edited_cb(self, cell, itr, value, key):
        # allow different input formats
        formats = ["%M", "%M:%S", "%M.%S"]
        
        if key == "duration":
            t = None
            
            for f in formats:
                try: 
                    t = time.strptime(value, f)
                    break
                except: 
                    continue
            
            if t is None: return
            
            value = t.tm_sec + 60 * t.tm_min
            
        self._model[itr][key] = value
                
        last = int(itr) == (len(self._model._obj) - 1)
        
        if last:
            self.add_addline()
    
    def _data_func(self, col, cell, model, itr, key):
        v = model[itr][0][key]
        
        if key == "duration":
            v = time.strftime("%M:%S", time.localtime(v))
        
        last = int(str(model.get_path(itr))) == (len(model) - 1)

        cell.set_property("style", Pango.Style.ITALIC if last else Pango.Style.NORMAL)
        
        cell.set_property("text", v)
        
class ListStore:
    FILE = xdg_data_home + "/teatime.js"
    
    def __init__(self, obj):
        self._obj = obj
        
        self.load()
    
    def load(self):        
        try:
            f = file(self.FILE)
            
            for t in json.load(f):
                self.append(t)
        except:
            pass
        else:
            f.close()
                
    def save(self):
        f = file(self.FILE, "w")

        json.dump([t[0] for t in self._obj][0:-1], f)
        
        f.close()
        
    def __getitem__(self, k):
        return self._obj[k][0]
    
    def __setitem__(self, k, v):
        self._obj[k][0] = v
    
    def append(self, v):
        self._obj.append((v,))
    
class Controller:
    def __init__(self):
        self.seen = None
        self.timer = None
                
        Notify.init("Tea Time")
        
        xml = Gtk.Builder()
        xml.add_from_file(DATA + "window.ui")
        
        self.le = Unity.LauncherEntry.get_for_desktop_file("teatime.desktop")
        
        self.label = xml.get_object("label1")
        
        self.start_button = xml.get_object("button1")
        self.start_button.connect("clicked", self.on_button_click)

        self.store = ListStore(xml.get_object("liststore1"))        
        self.list = TreeView(xml.get_object("treeview1"), self.store)
        self.list.add_addline()
                
        self.window = xml.get_object("window1")
        self.window.connect("delete-event", self.end)
        self.window.connect("window-state-event", self.window_state_event)
        self.window.show()
                        
        self.notification = Notification()
        self.main = GObject.MainLoop()
    
    def on_button_click(self, *a):
        if self.timer is None:
            self.start()
        else:
            self.stop()
    
    def set_label_text(self):
        name = self.timer.obj["name"]
        remaining = time.strftime("%M:%S", time.localtime(self.timer.end - time.time()))
        self.label.set_text(_("%s: %s remaining") % (name, remaining))
            
    def start(self):
        sel = self.list._obj.get_cursor()[0]
        self.timer = Timer(self.store[sel])
        self.timer.start()
        GObject.timeout_add_seconds(1, self.do_tick)
        
        self.le.set_property("progress_visible", True)
        self.le.set_property("progress", 0)
        
        self.start_button.set_label(_("Stop Timer"))
        self.list._obj.set_sensitive(False)
        
        self.set_label_text()
        
        self.window.iconify()
    
    def stop(self):
        self.le.set_property("urgent", False)
        self.le.set_property("progress_visible", False)
        self.start_button.set_label(_("Start Timer"))
        self.list._obj.set_sensitive(True)
        self.timer = None
        self.label.set_text(_("No Running Timers"))
             
    def run(self):
        self.main.run()        
    
    def show_notification(self):
        if not self.seen:
            self.notification.set_info(self.timer)
            self.notification.show()
            
        return not self.seen
    
    def start_notification_loop(self):
        self.seen = False
        self.show_notification()
        GObject.timeout_add_seconds(20, self.show_notification)
        
    def do_tick(self):
        if self.timer is None:
            return False # got cancelled
        
        p = self.timer.get_progress()
        self.le.set_property("progress", min(p, 1))
        
        self.set_label_text()
        
        if p >= 1:
            self.start_notification_loop()
            self.le.set_property("urgent", True)
        
        # if true gets called again
        return p < 1.0
               
    def end(self, *a):
        self.store.save()
        self.main.quit()
        
    def window_state_event(self, w, e):
        if e.changed_mask == Gdk.WindowState.ICONIFIED and not self.timer.running:
            self.seen = True
            self.stop()

c = Controller()
c.run()
