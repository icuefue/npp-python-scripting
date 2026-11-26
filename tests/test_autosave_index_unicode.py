# -*- coding: utf-8 -*-
import io
import os
import shutil
import sys
import tempfile
import time
import types
import unittest


class Dummy(object):
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class AutosaveIndexUnicodeTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        npp = types.ModuleType("Npp")
        npp.notepad = Dummy()
        npp.editor = Dummy()
        npp.console = Dummy()
        npp.NOTIFICATION = type("Notification", (), {"MODIFIED": 1})
        npp.STATUSBARSECTION = type("StatusBar", (), {"DOCTYPE": 1})
        previous_npp = sys.modules.get("Npp")
        previous_home = os.environ.get("HOME")
        sys.modules["Npp"] = npp
        os.environ["HOME"] = self.home
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "scripts", "Autosave", "Autosave.py"
            )
            module = types.ModuleType("autosave_unicode_test")
            module.__file__ = path
            with open(path, "rb") as source:
                eval(compile(source.read(), path, "exec"), module.__dict__)
            self.autosave = module
        finally:
            if previous_npp is None:
                del sys.modules["Npp"]
            else:
                sys.modules["Npp"] = previous_npp
            if previous_home is None:
                del os.environ["HOME"]
            else:
                os.environ["HOME"] = previous_home

    def test_index_displays_day_old_copies_with_unicode(self):
        a = self.autosave
        errors = []
        a.log = lambda message, level="INFO": errors.append((message, level))
        copies = [
            (1, u"plain.txt", u"plain content"),
            (6, u"árabe.txt", u"شارع جادة التنمية"),
        ]
        for days, name, content in copies:
            path = os.path.join(a.BACKUP_DIR, name)
            with io.open(path, "w", encoding="utf-8") as copy:
                copy.write(content)
            timestamp = time.time() - days * 86400 - 60
            os.utime(path, (timestamp, timestamp))

            a.generate_index()
            self.assertEqual(errors, [])

        with io.open(a.INDEX_FILE, "r", encoding="utf-8") as index:
            html = index.read()
        self.assertIn(u"hace 1 días", html)
        self.assertIn(u"hace 6 días", html)
        self.assertIn(u"شارع جادة التنمية", html)
        for days, name, content in copies:
            self.assertIn(name, html)


if __name__ == "__main__":
    unittest.main()
