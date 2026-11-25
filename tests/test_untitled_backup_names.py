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
        spec = importlib.util.spec_from_file_location(
            "autosave_test", Path(__file__).resolve().parents[1] / "Autosave.py"
        )
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

    def test_migration_preserves_content_metadata_and_saved_files(self):
        a = self.autosave
        old = self.write_copy("My Notes_abcdef12.txt")
        original_bytes = b"first\r\n\r\nsecond\r\n"
        old.write_bytes(original_bytes)
        saved = self.write_copy("report_abcdef12.txt", "file")
        target_base = a.get_backup_name(str(old), "2024-02-29_10-20-30")
        collision = self.directory / (target_base + ".txt")
        collision.write_text("do not overwrite", encoding="utf-8")

        a.migrate_untitled_copies(str(self.directory))
        target = self.directory / (target_base + "_2.txt")
        self.assertFalse(old.exists())
        self.assertFalse(Path(str(old) + ".meta.json").exists())
        self.assertEqual(target.read_bytes(), original_bytes)
        self.assertEqual(collision.read_text(), "do not overwrite")
        self.assertTrue(saved.exists())
        metadata = json.loads(Path(str(target) + ".meta.json").read_text())
        self.assertEqual(metadata["copy_name"], target.name)
        self.assertEqual(metadata["copy_path"], str(target))
        self.assertEqual(metadata["created_at"], "2024-02-29T10:20:30.123456")
        self.assertEqual(metadata["copy_count"], 4)
        a.migrate_untitled_copies(str(self.directory))
        self.assertTrue(target.exists())
        self.assertEqual(len(list(self.directory.glob("2024-02-29_10-20-30_*"))), 3)

    def test_failed_migration_retains_original_and_cleans_partial_copy(self):
        a = self.autosave
        old = self.write_copy("My Notes_abcdef12.txt")
        with mock.patch.object(a.shutil, "copyfileobj", side_effect=OSError("disk full")):
            a.migrate_untitled_copies(str(self.directory))
        self.assertEqual(old.read_text(), "original content")
        self.assertTrue(Path(str(old) + ".meta.json").exists())
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), [
            "My Notes_abcdef12.txt", "My Notes_abcdef12.txt.meta.json"
        ])

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

    def test_repairs_verified_bytes_and_keeps_damaged_file_and_metadata(self):
        a = self.autosave
        text = "first\r\n\r\nsecond\nthird\rfourth"
        expected = text.encode("utf-8")
        for directory in (self.directory, Path(a.OLD_DIR)):
            self.assertTrue(a.save_external_copy(str(directory), "damaged", text))
            copy = directory / "damaged.txt"
            copy.write_bytes(expected.replace(b"\n", b"\r\n"))
        metadata_path = self.directory / "damaged.txt.meta.json"
        metadata_before = metadata_path.read_bytes()
        self.assertEqual(a.repair_copy_newlines(), 2)
        self.assertEqual((self.directory / "damaged.txt").read_bytes(), expected)
        self.assertEqual((Path(a.OLD_DIR) / "damaged.txt").read_bytes(), expected)
        self.assertEqual(metadata_path.read_bytes(), metadata_before)
        backups = list((Path(a.META_DIR) / "newline_repairs").glob("*/damaged.txt"))
        self.assertEqual(len(backups), 2)
        for backup in backups:
            self.assertEqual(backup.read_bytes(), expected.replace(b"\n", b"\r\n"))
            self.assertTrue(Path(str(backup) + ".meta.json").exists())
        self.assertEqual(a.repair_copy_newlines(), 0)

    def test_repair_does_not_guess_when_metadata_is_missing_or_does_not_match(self):
        a = self.autosave
        missing_metadata = self.directory / "unverified.txt"
        missing_metadata.write_bytes(b"first\r\r\nsecond")
        self.assertTrue(a.save_external_copy(str(self.directory), "mismatch", "known\r\n"))
        mismatched = self.directory / "mismatch.txt"
        mismatched.write_bytes(b"different\r\r\n")
        self.assertEqual(a.repair_copy_newlines(), 0)
        self.assertEqual(missing_metadata.read_bytes(), b"first\r\r\nsecond")
        self.assertEqual(mismatched.read_bytes(), b"different\r\r\n")
        self.assertFalse((Path(a.META_DIR) / "newline_repairs").exists())

    def test_failed_repair_write_leaves_original_and_backup_intact(self):
        a = self.autosave
        self.assertTrue(a.save_external_copy(str(self.directory), "damaged", "first\r\n"))
        copy = self.directory / "damaged.txt"
        damaged = b"first\r\r\n"
        copy.write_bytes(damaged)
        with mock.patch.object(a.os, "fsync", side_effect=OSError("disk full")):
            self.assertEqual(a.repair_copy_newlines(), 0)
        self.assertEqual(copy.read_bytes(), damaged)
        backups = list((Path(a.META_DIR) / "newline_repairs").glob("*/damaged.txt"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), damaged)
        self.assertFalse(list(self.directory.glob(".newline-repair-*")))

    def test_repair_uses_windows_atomic_replacement_for_unicode_paths(self):
        a = self.autosave
        self.assertTrue(a.save_external_copy(str(self.directory), "reparar_\u00f1", "first\r\n"))
        copy = self.directory / "reparar_\u00f1.txt"
        copy.write_bytes(b"first\r\r\n")
        real_replace = os.replace

        def move_file(source, destination, flags):
            real_replace(source, destination)
            return 1

        with mock.patch.object(a.os, "name", "nt"), \
                mock.patch.object(a.ctypes, "windll", create=True) as windll:
            windll.kernel32.MoveFileExW.side_effect = move_file
            self.assertEqual(a.repair_copy_newlines(), 1)
            self.assertEqual(windll.kernel32.MoveFileExW.call_args.args[1:], (str(copy), 0x9))
        self.assertEqual(copy.read_bytes(), b"first\r\n")

    def test_aggressive_repair_collapses_only_three_or_more_logical_line_breaks(self):
        a = self.autosave
        cases = [
            ("a\r\nb\r\n\r\nc\r\n\r\n\r\nd\r\n\r\n\r\n\r\n",
             "a\r\nb\r\n\r\nc\r\nd\r\n"),
            ("a\nb\n\nc\n\n\nd\n\n\n\n", "a\nb\n\nc\nd\n"),
            ("a\rb\r\rc\r\r\rd\r\r\r\r", "a\rb\r\rc\rd\r"),
            ("a\r\n\n\rb\n\r\nc\r\r\nd", "a\r\nb\n\r\nc\r\r\nd"),
        ]
        for index, (text, expected) in enumerate(cases):
            with self.subTest(text=repr(text)):
                name = "aggressive_{}".format(index)
                self.assertTrue(a.save_external_copy(str(self.directory), name, text))
                copy = self.directory / (name + ".txt")
                metadata_before = a.load_copy_metadata(str(copy))
                self.assertEqual(a.repair_copy_newlines(aggressive=True), 1)
                self.assertEqual(copy.read_bytes(), expected.encode("utf-8"))
                metadata = a.load_copy_metadata(str(copy))
                self.assertEqual(metadata["sha256"], hashlib.sha256(copy.read_bytes()).hexdigest())
                self.assertEqual(metadata["size_bytes"], len(copy.read_bytes()))
                self.assertEqual(metadata["line_count"], len(expected.splitlines()))
                self.assertEqual(metadata["created_at"], metadata_before["created_at"])
                self.assertEqual(metadata["copy_count"], metadata_before["copy_count"])
                backups = list((Path(a.META_DIR) / "newline_repairs").glob("*/" + copy.name))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), text.encode("utf-8"))
        self.assertEqual(a.repair_copy_newlines(aggressive=True), 0)

    def test_aggressive_repair_handles_archived_copies_without_metadata(self):
        a = self.autosave
        copy = Path(a.OLD_DIR) / "without_metadata.txt"
        damaged = "primera \u00f1\r\n\r\n\r\nsegunda".encode("utf-8")
        copy.write_bytes(damaged)
        self.assertEqual(a.repair_copy_newlines(aggressive=True), 1)
        self.assertEqual(copy.read_bytes(), "primera \u00f1\r\nsegunda".encode("utf-8"))
        metadata = a.load_copy_metadata(str(copy))
        self.assertEqual(metadata["sha256"], hashlib.sha256(copy.read_bytes()).hexdigest())
        self.assertEqual(metadata["character_count"], len("primera \u00f1\r\nsegunda"))
        backups = list((Path(a.META_DIR) / "newline_repairs").glob("*/" + copy.name))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), damaged)


if __name__ == "__main__":
    unittest.main()
