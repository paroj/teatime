#!/usr/bin/env python3

from setuptools import setup
from DistUtilsExtra.command import build_i18n, build_extra

#DEST="/opt/extras.ubuntu.com/teatime/"
DEST="bin/"

class my_build_i18n(build_i18n.build_i18n):
    def run(self):
        build_i18n.build_i18n.run(self)
        
        df = self.distribution.data_files
        
        self.distribution.data_files = [(d.replace("share/locale/", DEST+"locale/"), s) for d, s in df]

setup(
      cmdclass = {"build": build_extra.build_extra,
                  "build_i18n": my_build_i18n},
      name = "teatime",
      version = "18.03",
      description = "A simple egg timer application for the Unity Desktop",
      author = "Pavel Rojtberg",
      author_email = "pavel@rojtberg.net",
      url = "http://www.rojtberg.net/",
      license = "GNU GPL v3",
      data_files = [("share/applications/", ["teatime.desktop"]),
                    (DEST, ["window.ui", "teatime.py"])])
