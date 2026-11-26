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
        npp.NOTIFICATION = types.SimpleNamespace(MODIFIED=1, BUFFERACTIVATED=4)
        npp.SCINTILLANOTIFICATION = types.SimpleNamespace(MODIFIED=2, UPDATEUI=3)
        npp.STATUSBARSECTION = types.SimpleNamespace(DOCTYPE=1)
        self.npp = npp
        spec = importlib.util.spec_from_file_location(
            "autosave_test",
            Path(__file__).resolve().parents[1] / "scripts" / "Autosave" / "Autosave.py",
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

    def test_generated_copyright_notices_identify_icuefue(self):
        a = self.autosave
        year = datetime.datetime.now().year
        config = Path(a.CONFIG_FILE).read_text(encoding="utf-8")
        html = Path(a.INDEX_FILE).read_text(encoding="utf-8")
        log = Path(a.LOG_FILE).read_text(encoding="utf-8")
        self.assertIn("# © {} icuefue".format(year), config)
        self.assertIn("&copy; {} icuefue".format(year), html)
        self.assertIn("© {} icuefue".format(year), log)

    def test_status_reports_when_autosave_is_stopped(self):
        a = self.autosave
        saver = a._autosaver
        saver.running = False
        saver.timer_id = None
        messages = []

        with mock.patch.object(a, "log", side_effect=messages.append):
            self.assertEqual(
                a.status(),
                "Autosave detenido. No hay copias automáticas programadas.",
            )
        self.assertEqual(messages, [
            "Autosave detenido. No hay copias automáticas programadas."
        ])
        a.notepad.messageBox.assert_not_called()

    def test_status_reports_next_periodic_copy(self):
        a = self.autosave
        saver = a._autosaver
        saver.running = True
        saver.timer_id = 1
        saver.last_tick = 199.9
        saver.last_interval = 100.0
        saver.pending_idle_save = False

        with mock.patch.object(a, "get_interval_time", return_value=300):
            self.assertEqual(
                saver.get_status_message(now=200.1),
                "Autosave activo. Próxima copia periódica en 3 min 20 s.",
            )

    def test_status_prefers_pending_idle_copy_when_it_is_sooner(self):
        a = self.autosave
        saver = a._autosaver
        saver.running = True
        saver.timer_id = 1
        saver.last_interval = 100.0
        saver.pending_idle_save = True
        saver.last_change = 350.5
        saver.last_tick = 350.0
        messages = []

        with mock.patch.object(a, "get_interval_time", return_value=300), \
                mock.patch.object(a, "get_idle_time", return_value=10), \
                mock.patch.object(a.time, "time", return_value=350.5), \
                mock.patch.object(a, "log", side_effect=messages.append):
            self.assertEqual(
                saver.get_status_message(now=355.0),
                "Autosave activo. Próxima copia por inactividad en 6 s.",
            )
            self.assertEqual(
                a.status(),
                "Autosave activo. Próxima copia por inactividad en 10 s.",
            )
        self.assertEqual(messages, [
            "Autosave activo. Próxima copia por inactividad en 10 s."
        ])

    def test_status_reports_stalled_timer_instead_of_zero_countdown(self):
        a = self.autosave
        saver = a._autosaver
        saver.running = True
        saver.timer_id = 1
        saver.last_tick = 100.0
        saver.pending_idle_save = True
        saver.last_change = 100.0

        self.assertEqual(
            saver.get_status_message(now=160.0),
            "Autosave activo, pero el temporizador no responde (último aviso "
            "hace 60 s). No se están haciendo copias automáticas; vuelve a "
            "cargar Autosave.",
        )

    def test_start_off_ui_thread_defers_timer_to_ui_notification(self):
        a = self.autosave
        a._autosaver.stop()
        saver = a.AutoSaver()
        created = []

        def create_timer():
            created.append(True)
            saver.timer_id = 7

        with mock.patch.object(saver, "_on_ui_thread", return_value=False), \
                mock.patch.object(saver, "_create_timer", side_effect=create_timer):
            saver.start()
            self.assertEqual(created, [])
            self.assertIn("temporizador aún no está en marcha",
                          saver.get_status_message())
            a.editor.callbackSync.assert_called_with(saver.ensure_timer, [3])
            a.notepad.callback.assert_called_with(saver.ensure_timer, [4])

            saver.ensure_timer({})
            saver.ensure_timer({})

        self.assertEqual(created, [True])

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

    def test_index_handles_utf8_names_and_non_ascii_content(self):
        a = self.autosave
        name = (
            "direcci\u00f3n_\u0634\u0627\u0631\u0639 "
            "\u062c\u0627\u062f\u0629 \u0627\u0644\u062a\u0646\u0645\u064a\u0629.txt"
        )
        content = (
            "7871 Jada Al Tanmyah St. ("
            "\u0634\u0627\u0631\u0639 \u062c\u0627\u062f\u0629 "
            "\u0627\u0644\u062a\u0646\u0645\u064a\u0629"
            ")\nKing Abdullah Economic City"
        )
        backup = self.directory / name
        backup.write_text(content, encoding="utf-8")
        Path(str(backup) + ".meta.json").write_text(json.dumps({
            "original_name": name,
            "original_path": "C:\\Documents\\{}".format(name),
        }, ensure_ascii=False), encoding="utf-8")

        real_listdir = a.os.listdir

        def utf8_filenames(path):
            return [
                entry.encode("utf-8") if isinstance(entry, str) else entry
                for entry in real_listdir(path)
            ]

        with mock.patch.object(a.os, "listdir", side_effect=utf8_filenames):
            a.generate_index()

        html = Path(a.INDEX_FILE).read_text(encoding="utf-8")
        self.assertIn(name, html)
        self.assertIn("\u0634\u0627\u0631\u0639 \u062c\u0627\u062f\u0629 \u0627\u0644\u062a\u0646\u0645\u064a\u0629", html)
        self.assertNotIn("b&#x27;", html)

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
