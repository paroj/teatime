#!/usr/bin/env python3

import time
import json
import locale
import subprocess
import os

import gi
gi.require_version("Unity", "7.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import Unity, GObject, Gtk, Notify, Gdk, Pango, GLib, Gio

GETTEXT_DOMAIN = "teatime"

# should use libcanberra, but no python bindings so far..
SOUND_ALERT_FILE = "/usr/share/sounds/freedesktop/stereo/complete.oga"

REMIND_DELTA_SECONDS = 30

# DATA = os.path.expanduser("~/workspace/teatime/")
DATA = "/usr/bin/"

if "SNAP" in os.environ:
    DATA = os.environ["SNAP"] + DATA[4:]  # $SNAP/bin/
    SOUND_ALERT_FILE = os.environ["SNAP"] + "/data-dir/sounds/freedesktop/stereo/complete.oga"

# use locale instead of gettext, so GTK gets the change
locale.bindtextdomain(GETTEXT_DOMAIN, DATA + "locale/")
locale.textdomain(GETTEXT_DOMAIN)
_ = locale.gettext


class Notification(Notify.Notification):

    def __init__(self):
        Notify.Notification.__init__(self)
        self.set_urgency(Notify.Urgency.LOW)

    def set_info(self, timer):
        elapsed = time.time() - timer.end

        if elapsed < 20:
            body = _("finished just now")
        elif elapsed < 60:
            body = _("finished %s seconds ago") % time.strftime("%S", time.localtime(elapsed))
        else:
            body = _("finished %s minutes ago") % time.strftime("%M:%S", time.localtime(elapsed))

        self.update(_("%s is ready") % timer.obj["name"], body, None)


class Timer:

    def __init__(self, obj):
        if obj["duration"] == 0:
            raise ValueError

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
        self._cells = []

        transl = (("name", _("Name")), ("duration", _("Duration")))

        for key, title in transl:
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            cell.set_property("editable", True)
            cell.connect("edited", self._edited_cb, key)
            self._cells.append(cell)

            col = Gtk.TreeViewColumn(title, cell)
            col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            col.set_min_width(100)
            col.set_fixed_width(200)
            col.set_cell_data_func(cell, self._data_func, key)
            self._obj.append_column(col)

        # configure search
        obj.set_search_column(0)
        obj.set_search_equal_func(self._search_eq_fn)

    def _search_eq_fn(self, model, col, key, itr):
        # case insensitive prefix search
        name = model[itr][col]["name"].lower()
        # invert result as needed by GTK API
        return not name.startswith(key.lower())

    def add_addline(self):
        self._model.append({"name": _("New Entry"), "duration":0})

    def in_edit(self):
        return any([c.get_property("editing") for c in self._cells])

    def _edited_cb(self, cell, itr, value, key):
        # allow different input formats
        formats = ["%M", "%M:%S", "%M.%S", "%H:%M:%S"]

        if key == "duration":
            t = None

            for f in formats:
                try:
                    t = time.strptime(value, f)
                    break
                except:
                    continue

            if t is None: return

            value = t.tm_sec + 60 * t.tm_min + 60 * 60 * t.tm_hour
        else:
            value = value  # .decode("utf-8") # for consistency, obsolete in python3??

        self._model[itr][key] = value

        last = int(itr) == (len(self._model._obj) - 1)

        if last:
            self.add_addline()

    def _data_func(self, col, cell, model, itr, key):
        v = model[itr][0][key]

        if key == "duration":
            if v >= 60 * 60:
                v = time.strftime("%H:%M:%S", time.gmtime(v))
            else:
                v = time.strftime("%M:%S", time.gmtime(v))

        last = int(str(model.get_path(itr))) == (len(model) - 1)

        cell.set_property("style", Pango.Style.ITALIC if last else Pango.Style.NORMAL)

        cell.set_property("text", v)


class ListStore:
    FILE = GLib.get_user_data_dir() + "/teatime.js"

    def __init__(self, obj):
        self._obj = obj

        self.load()

    def load(self):
        try:
            f = open(self.FILE)

            for t in json.load(f):
                self.append(t)
        except:
            pass
        else:
            f.close()

    def save(self):
        f = open(self.FILE, "w")

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
        self.notify_src = None
        self.tick_src = None

        Notify.init("Tea Time")

        xml = Gtk.Builder()
        xml.set_translation_domain(GETTEXT_DOMAIN)
        xml.add_from_file(DATA + "window.ui")

        xml.connect_signals({"hide-widget": lambda w, *args: w.hide_on_delete()})

        desktop_file_name = "teatime.desktop"
        self.window = xml.get_object("window1")

        if "SNAP" in os.environ:
            desktop_file_name = "teatime_teatime.desktop"
            icon = os.environ["SNAP"]+"/meta/gui/icon.svg"
            self.window.set_default_icon_from_file(icon)
            xml.get_object("aboutdialog1").set_logo(None)


        self.app = Gtk.Application(application_id="net.rojtberg.teatime")
        self.app.connect("startup", self._startup, xml)
        self.app.connect("activate", lambda *args: self.window.present())

        self.le = Unity.LauncherEntry.get_for_desktop_file(desktop_file_name)

    def _startup(self, app, xml):
        # appmenu
        app.set_app_menu(xml.get_object("app-menu"))

        action = Gio.SimpleAction.new("about", None)
        about = xml.get_object("aboutdialog1")
        action.connect("activate", lambda *args: about.show())
        app.add_action(action)

        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.end)
        app.add_action(action)

        self.label = xml.get_object("label1")

        self.start_button = xml.get_object("button1")
        self.start_button.connect("clicked", self.on_button_click)

        self.store = ListStore(xml.get_object("liststore1"))
        self.list = TreeView(xml.get_object("treeview1"), self.store)
        self.list._obj.connect("cursor-changed", self.on_sel_changed)
        self.list.add_addline()

        self.window.set_application(app)
        self.window.connect("delete-event", self.end)
        self.window.connect("window-state-event", self.timer_noticed)
        self.window.connect("focus-in-event", self.timer_noticed)
        self.window.connect("key-press-event", self.on_key_press)
        self.window.show()

        self.notification = Notification()

    def on_key_press(self, caller, ev):
        key = Gdk.keyval_name(ev.keyval)

        if key == "Delete" and not self.list.in_edit():
            # dont allow deleting addline
            if self.sel == len(self.store._obj) - 1:
                return

            itr = self.store._obj.get_iter(self.sel)
            self.store._obj.remove(itr)

    def on_sel_changed(self, *a):
        self.sel = self.list._obj.get_cursor()[0]

        if self.sel is None:
            # happens on delete?
            return

        self.sel = int(str(self.sel))

        self.start_button.set_sensitive(not (self.sel == len(self.store._obj) - 1))

    def on_button_click(self, *a):
        if self.timer is None:
            try:
                self.start()
            except ValueError:  # gets thrown by timer if duration == 0
                pass
        else:
            self.stop()

    def set_label_text(self):
        name = self.timer.obj["name"]

        dt = self.timer.end - time.time()

        if dt <= 0:
            self.label.set_text(_("%s is ready") % name)
            return

        t = time.gmtime(dt)
        f = "%H:%M:%S" if t.tm_hour > 0 else "%M:%S"

        remaining = time.strftime(f, t)
        self.label.set_text(_("%s: %s remaining") % (name, remaining))

    def start(self):
        self.timer = Timer(self.store[self.sel])
        self.timer.start()
        self.tick_src = GObject.timeout_add_seconds(1, self.do_tick)

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

        if self.tick_src is not None:
            GObject.source_remove(self.tick_src)
            self.tick_src = None

        if self.notify_src is not None:
            GObject.source_remove(self.notify_src)
            self.notify_src = None

    def run(self):
        self.app.run()

    def show_notification(self):
        if not self.seen:
            self.notification.set_info(self.timer)
            self.notification.show()
            subprocess.Popen(["canberra-gtk-play", "-f", SOUND_ALERT_FILE])

        return not self.seen

    def start_notification_loop(self):
        self.seen = False
        self.show_notification()
        self.notify_src = GObject.timeout_add_seconds(REMIND_DELTA_SECONDS, self.show_notification)

    def do_tick(self):
        p = self.timer.get_progress()
        self.le.set_property("progress", min(p, 1))

        self.set_label_text()

        if p >= 1:
            self.start_notification_loop()
            self.le.set_property("urgent", True)

        # if true gets called again
        if p < 1.0:
            return True
        else:
            self.tick_src = None
            return False

    def end(self, *a):
        self.stop()
        self.store.save()
        self.app.quit()

    def timer_noticed(self, *a):
        if self.timer and not self.timer.running:
            self.seen = True
            self.stop()


if __name__ == "__main__":
    c = Controller()
    c.run()
