#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *

setup(
      cmdclass = {"build": build_extra.build_extra,
                  "build_i18n":  build_i18n.build_i18n},
      name = "teatime",
      version = "11.10",
      description = "a tea timer",
      author = "Pavel Rojtberg",
      author_email = "pavel@rojtberg.net",
      url = "http://www.rojtberg.net/",
      license = "GNU GPL v3",
      scripts = ["teatime.py"],
      data_files = [("share/applications/", ["teatime.desktop"]),
                    ("share/teatime/", ["window.ui"])])
