#!/usr/bin/env python

import time
from gi.repository import Unity, GObject, Gtk, Dbusmenu, Notify, Gdk

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
            
        self.update("%s is ready" % timer.obj.title, body, None)

class TimedObject:
    def __init__(self, title, duration):
        self.title = title
        self.duration = duration

class Timer:
    def __init__(self, obj):
        self.obj = obj
        self.begin = None
        self.end = None
    
    def start(self):
        self.begin = time.time()
        self.end = self.begin + self.obj.duration
    
    def get_progress(self):
        t = time.time()
        progress = (t - self.begin)/self.obj.duration
        
        return progress

class Controller:
    def __init__(self):
        self.seen = True
        self.timer = Timer(test)
        
        self.le = Unity.LauncherEntry.get_for_desktop_file("teatime.desktop")
        
        Notify.init("Tea Time")
        
        xml = Gtk.Builder()
        xml.add_from_file("/home/pavel/workspace/teatime/window.ui")
        
        xml.get_object("button1").connect("clicked", self.start)
        
        self.window = xml.get_object("window1")
        self.window.connect("delete-event", self.end)
        self.window.connect("window-state-event", self.window_state_event)
        self.window.show()
                        
        self.notification = Notification()
        self.main = GObject.MainLoop()
    
    def start(self, *a):
        self.timer.start()
        GObject.timeout_add_seconds(1, self.do_tick)
        
        self.le.set_property("progress_visible", True)
        self.le.set_property("progress", 0)
        
        self.window.iconify()
    
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
        p = self.timer.get_progress()
        self.le.set_property("progress", min(p, 1))
        
        if p >= 1:
            self.start_notification_loop()
            self.le.set_property("urgent", True)
        
        # if true gets called again
        return p < 1.0
               
    def end(self, *a):
        self.main.quit()
    
    def window_state_event(self, w, e):
        if e.changed_mask == Gdk.WindowState.ICONIFIED and not self.seen:
            self.seen = True
            self.le.set_property("urgent", False)
            self.le.set_property("progress_visible", False)

earl_grey = TimedObject("Earl Grey", 3.5*60)
test = TimedObject("Test", 2)

c = Controller()

ql = Dbusmenu.Menuitem.new ()
item1 = Dbusmenu.Menuitem.new ()
item1.property_set (Dbusmenu.MENUITEM_PROP_LABEL, "Pause")
item1.property_set_bool (Dbusmenu.MENUITEM_PROP_VISIBLE, True)
item2 = Dbusmenu.Menuitem.new ()
item2.property_set (Dbusmenu.MENUITEM_PROP_LABEL, "Restart")
item2.property_set_bool (Dbusmenu.MENUITEM_PROP_VISIBLE, True)
ql.child_append (item1)
ql.child_append (item2)
c.le.set_property("quicklist", ql)

c.run()
