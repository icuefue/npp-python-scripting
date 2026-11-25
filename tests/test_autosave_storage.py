from pathlib import Path
import tempfile
import unittest
from unittest import mock

import AutosaveStorage as storage


class StorageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / "old"
        self.new = self.root / "new"
        self.old.mkdir()
        self.locator = self.root / "locator"
        patch = mock.patch.object(storage, "LOCATOR_FILE", str(self.locator))
        patch.start()
        self.addCleanup(patch.stop)
        default = mock.patch.object(storage, "default_base_dir", return_value=str(self.old))
        default.start()
        self.addCleanup(default.stop)

    def config(self, base):
        (self.old / "config.txt").write_text(
            "idle_time = 17\nbase_dir = {}\n".format(base), encoding="utf-8"
        )

    def test_migrates_all_files_overwrites_and_retains_source(self):
        self.config(self.new)
        storage.write_locator(str(self.old))
        (self.old / "_backup").mkdir()
        (self.old / "_backup" / "copy.txt").write_text("source", encoding="utf-8")
        (self.old / "_backup" / "copy.txt.meta.json").write_text("metadata", encoding="utf-8")
        (self.old / "_protocol").mkdir()
        (self.old / "_protocol" / "settings.json").write_text("old", encoding="utf-8")
        (self.old / "extra").mkdir()
        (self.old / "extra" / "file").write_text("extra", encoding="utf-8")
        (self.new / "_backup").mkdir(parents=True)
        (self.new / "_backup" / "copy.txt").write_text("destination", encoding="utf-8")

        def register(base):
            self.assertEqual(base, str(self.new))
            self.assertEqual(storage.active_base_dir(), str(self.old))
            self.assertEqual((self.new / "_backup" / "copy.txt").read_text(), "source")

        self.assertEqual(storage.prepare_storage(register), str(self.new))
        self.assertEqual(storage.active_base_dir(), str(self.new))
        self.assertEqual((self.new / "extra" / "file").read_text(), "extra")
        self.assertEqual((self.new / "_backup" / "copy.txt.meta.json").read_text(), "metadata")
        self.assertEqual((self.old / "_backup" / "copy.txt").read_text(), "source")
        self.assertEqual(storage.configured_base_dir(str(self.new / "config.txt")), str(self.new))
        self.assertEqual(storage.prepare_storage(register), str(self.new))

    def test_copy_failure_keeps_original_active_and_surfaces_error(self):
        self.config(self.new)
        storage.write_locator(str(self.old))
        (self.old / "data.txt").write_text("safe", encoding="utf-8")
        with mock.patch.object(storage.shutil, "copy2", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                storage.prepare_storage(mock.Mock())
        self.assertEqual(storage.active_base_dir(), str(self.old))
        self.assertEqual((self.old / "data.txt").read_text(), "safe")

    def test_protocol_failure_does_not_activate_destination(self):
        self.config(self.new)
        storage.write_locator(str(self.old))
        (self.old / "_protocol").mkdir()
        (self.old / "_protocol" / "settings.json").write_text("old", encoding="utf-8")
        with self.assertRaisesRegex(OSError, "denied"):
            storage.prepare_storage(mock.Mock(side_effect=OSError("denied")))
        self.assertEqual(storage.active_base_dir(), str(self.old))

    def test_locator_failure_restores_protocol_and_keeps_old_directory(self):
        self.config(self.new)
        storage.write_locator(str(self.old))
        (self.old / "_protocol").mkdir()
        (self.old / "_protocol" / "settings.json").write_text("old", encoding="utf-8")
        register = mock.Mock()
        with mock.patch.object(storage, "write_locator", side_effect=OSError("denied")):
            with self.assertRaisesRegex(OSError, "denied"):
                storage.prepare_storage(register)
        self.assertEqual(register.call_args_list, [
            mock.call(str(self.new)), mock.call(str(self.old))
        ])
        self.assertEqual(storage.active_base_dir(), str(self.old))

    def test_destination_inside_source_is_not_copied_recursively(self):
        destination = self.old / "nested"
        self.config(destination)
        storage.write_locator(str(self.old))
        (self.old / "file.txt").write_text("data", encoding="utf-8")
        self.assertEqual(storage.prepare_storage(mock.Mock()), str(destination))
        self.assertEqual((destination / "file.txt").read_text(), "data")
        self.assertFalse((destination / "nested").exists())

    def test_destination_containing_source_is_rejected(self):
        self.config(self.root)
        storage.write_locator(str(self.old))
        with self.assertRaisesRegex(ValueError, "contener"):
            storage.prepare_storage(mock.Mock())
        self.assertEqual(storage.active_base_dir(), str(self.old))

    def test_legacy_config_is_copied_to_existing_data_directory(self):
        self.new.mkdir()
        (self.new / "existing.txt").write_text("keep", encoding="utf-8")
        self.config(self.new)
        (self.old / "_protocol").mkdir()
        (self.old / "_protocol" / "settings.json").write_text("old", encoding="utf-8")
        register = mock.Mock()
        self.assertEqual(storage.prepare_storage(register), str(self.new))
        self.assertEqual(storage.active_base_dir(), str(self.new))
        self.assertEqual((self.new / "existing.txt").read_text(), "keep")
        self.assertTrue((self.new / "_protocol" / "settings.json").exists())
        self.assertTrue((self.old / "config.txt").exists())
        register.assert_called_once_with(str(self.new))

    def test_relative_target_is_resolved_once(self):
        self.config("../new")
        storage.write_locator(str(self.old))
        self.assertEqual(storage.prepare_storage(mock.Mock()), str(self.new))
        self.assertEqual(storage.prepare_storage(mock.Mock()), str(self.new))


if __name__ == "__main__":
    unittest.main()
