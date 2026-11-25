import datetime
import binascii
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


class UntitledBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        npp = types.ModuleType("Npp")
        npp.notepad = mock.Mock()
        npp.editor = mock.Mock()
        npp.console = mock.Mock()
        npp.NOTIFICATION = types.SimpleNamespace(MODIFIED=1)
        npp.STATUSBARSECTION = types.SimpleNamespace(DOCTYPE=1)
        self.npp = npp
        spec = importlib.util.spec_from_file_location(
            "autosave_test", Path(__file__).resolve().parents[1] / "Autosave.py"
        )
        self.spec = spec
        self.autosave = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"Npp": npp}), mock.patch.dict(
            os.environ, {"HOME": self.temp.name}
        ):
            spec.loader.exec_module(self.autosave)
        self.directory = Path(self.autosave.BACKUP_DIR)
        self.now = datetime.datetime(2026, 11, 25, 15, 30, 0)

    def write_copy(self, name, source_type="untitled_buffer"):
        path = self.directory / name
        path.write_text("original content", encoding="utf-8")
        metadata = {
            "source_type": source_type,
            "created_at": "2024-02-29T10:20:30.123456",
            "copy_name": name,
            "copy_path": str(path),
            "copy_count": 4,
        }
        Path(str(path) + ".meta.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        return path

    def test_startup_leaves_existing_copy_names_and_contents_unchanged(self):
        copy = self.write_copy("My Notes_abcdef12.txt")
        content = b"first\r\n\r\n\r\nsecond\r\n"
        copy.write_bytes(content)
        metadata_path = Path(str(copy) + ".meta.json")
        metadata = metadata_path.read_bytes()
        with mock.patch.dict(sys.modules, {"Npp": self.npp}), mock.patch.dict(
            os.environ, {"HOME": self.temp.name}
        ):
            self.spec.loader.exec_module(self.autosave)
        self.assertEqual(copy.read_bytes(), content)
        self.assertEqual(metadata_path.read_bytes(), metadata)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), [
            copy.name, metadata_path.name
        ])

    def test_new_copy_is_stable_and_avoids_existing_files(self):
        a = self.autosave
        with mock.patch.object(a, "datetime", wraps=datetime.datetime) as clock:
            clock.now.return_value = self.now
            base = a.get_backup_name("untitled-buffer-5", "2026-11-25_15-30-00")
            (self.directory / (base + ".txt")).write_text("keep", encoding="utf-8")
            name = a.get_untitled_copy_name(5, "first line", 0)
            self.assertEqual(name, base + "_2")
            self.assertTrue(a.save_external_copy(
                str(self.directory), name, "first", source_type="untitled_buffer"
            ))
            clock.now.return_value = self.now + datetime.timedelta(hours=1)
            self.assertEqual(a.get_untitled_copy_name(5, "changed", 0), name)
            self.assertTrue(a.save_external_copy(
                str(self.directory), name, "changed", source_type="untitled_buffer"
            ))
        self.assertEqual((self.directory / (name + ".txt")).read_text(), "changed")
        self.assertEqual((self.directory / (base + ".txt")).read_text(), "keep")

    def test_idle_and_interval_saves_reuse_the_same_untitled_copy(self):
        a = self.autosave
        a.notepad.getCurrentBufferID.return_value = 5
        a.notepad.getCurrentFilename.return_value = "new 1"
        a.notepad.getFiles.return_value = [("new 1", 5)]
        a.editor.getModify.return_value = True
        a.editor.getText.return_value = "first line"
        with mock.patch.object(a, "datetime", wraps=datetime.datetime) as clock:
            clock.now.return_value = self.now
            self.assertTrue(a.save_current_buffer())
            a.editor.getText.return_value = "changed line"
            clock.now.return_value += datetime.timedelta(hours=1)
            self.assertTrue(a.save_buffer(5, 0))
        copies = list(self.directory.glob("*.txt"))
        self.assertEqual(len(copies), 1)
        self.assertTrue(copies[0].name.startswith("2026-11-25_15-30-00_"))
        self.assertEqual(copies[0].read_text(), "changed line")

    def test_index_links_address_backup_names_not_originals(self):
        a = self.autosave
        backup = self.write_copy("report_\u00f1 & [1].txt", "file")
        archive = Path(a.OLD_DIR) / backup.name
        archive.write_text("archived", encoding="utf-8")
        expected = "npp-autosave:backup/" + binascii.hexlify(
            backup.name.encode("utf-8")
        ).decode("ascii")
        self.assertEqual(a.copy_url(str(backup)), expected)
        with mock.patch.object(a.sys, "getfilesystemencoding", return_value="cp1252"):
            self.assertEqual(a.copy_url(str(backup).encode("cp1252")), expected)
        self.assertEqual(a.copy_url(str(archive)), expected.replace(":backup/", ":old/"))
        with self.assertRaises(ValueError):
            a.copy_url(str(Path(self.temp.name) / backup.name))
        a.generate_index()
        html = Path(a.INDEX_FILE).read_text(encoding="utf-8")
        self.assertIn('href="{}" class="file-link"'.format(expected), html)
        self.assertNotIn(a.file_url(str(backup)), html)

    def test_windows_copies_preserve_line_endings_and_metadata_hash(self):
        a = self.autosave
        real_open = io.open

        def windows_open(path, mode="r", *args, **kwargs):
            if "w" in mode and "b" not in mode and kwargs.get("newline") is None:
                kwargs["newline"] = "\r\n"
            return real_open(path, mode, *args, **kwargs)

        texts = [
            "first\r\nsecond\r\n",
            "first\nsecond\n",
            "first\rsecond\r",
            "first\r\n\r\nsecond\nthird\rfourth",
        ]
        with mock.patch.object(a.io, "open", side_effect=windows_open):
            for index, text in enumerate(texts):
                with self.subTest(text=repr(text)):
                    name = "line_endings_{}".format(index)
                    self.assertTrue(a.save_external_copy(str(self.directory), name, text))
                    copy = self.directory / (name + ".txt")
                    expected = text.encode("utf-8")
                    self.assertEqual(copy.read_bytes(), expected)
                    metadata = a.load_copy_metadata(str(copy))
                    self.assertEqual(metadata["sha256"], hashlib.sha256(expected).hexdigest())
                    self.assertEqual(metadata["size_bytes"], len(expected))
                    self.assertTrue(a.save_external_copy(
                        str(self.directory), name, text, force=True
                    ))
                    self.assertEqual(copy.read_bytes(), expected)

if __name__ == "__main__":
    unittest.main()
