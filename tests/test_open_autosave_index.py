import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock
from urllib.parse import unquote
import AutosaveStorage


class OpenAutosaveIndexTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name) / "profile with spaces_\u00f1"
        home = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        home.start()
        self.addCleanup(home.stop)
        self.config_dir = self.home / "Documents" / "NPP"
        self.config_dir.mkdir(parents=True)
        locator = mock.patch.object(
            AutosaveStorage, "LOCATOR_FILE", str(self.home / "locator")
        )
        locator.start()
        self.addCleanup(locator.stop)
        self.notepad = mock.Mock()
        spec = importlib.util.spec_from_file_location(
            "open_index_test", Path(__file__).resolve().parents[1] / "OpenAutosaveIndex.py"
        )
        self.script = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"Npp": types.SimpleNamespace(notepad=self.notepad)}):
            spec.loader.exec_module(self.script)

    def test_resolves_active_directory_not_pending_configuration(self):
        self.assertEqual(self.script.get_index_path(), str(self.config_dir / "index.html"))
        config = self.config_dir / "config.txt"
        config.write_text('# comment\nbase_dir = "copias"\n', encoding="utf-8")
        AutosaveStorage.write_locator(str(self.config_dir))
        self.assertEqual(self.script.get_index_path(), str(self.config_dir / "index.html"))
        active = self.home / "copias"
        active.mkdir()
        (active / "config.txt").write_text("base_dir = {}\n".format(active), encoding="utf-8")
        AutosaveStorage.write_locator(str(active))
        self.assertEqual(self.script.get_index_path(), str(active / "index.html"))

    def test_registers_before_opening_browser_and_reports_missing_index(self):
        with mock.patch.object(self.script, "register_protocol") as register, \
                mock.patch.object(self.script.webbrowser, "open") as browser:
            self.assertFalse(self.script.open_autosave_index())
            register.assert_not_called()
            browser.assert_not_called()
            index = self.config_dir / "index.html"
            index.write_text("<html></html>", encoding="utf-8")
            browser.side_effect = lambda url: register.assert_called_once_with(
                str(self.config_dir)
            ) or True
            self.assertTrue(self.script.open_autosave_index())
            self.assertEqual(unquote(browser.call_args[0][0]), "file:///" + str(index))
            self.notepad.open.assert_not_called()

    def test_registration_failure_prevents_opening_nonworking_links(self):
        (self.config_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        with mock.patch.object(self.script, "register_protocol", side_effect=OSError("denied")), \
                mock.patch.object(self.script.webbrowser, "open") as browser:
            self.assertFalse(self.script.open_autosave_index())
            browser.assert_not_called()
            self.assertIn("denied", self.notepad.messageBox.call_args[0][0])

    def test_python2_passes_utf8_error_messages_to_notepad(self):
        with mock.patch.object(self.script.sys, "version_info", (2, 7, 18)):
            self.assertFalse(self.script.open_autosave_index())
            message = self.notepad.messageBox.call_args[0][0]
            self.assertIsInstance(message, bytes)
            self.assertIn(str(self.config_dir), message.decode("utf-8"))

    def test_installs_current_user_protocol_with_current_notepad_and_base_dir(self):
        npp_dir = self.home / "Notepad++"
        npp_dir.mkdir()
        (npp_dir / "notepad++.exe").touch()
        self.notepad.getNppDir.return_value = str(npp_dir).encode("utf-8")
        system_root = self.home / "Windows"
        powershell = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        powershell.parent.mkdir(parents=True)
        powershell.touch()
        registry = mock.MagicMock()
        base_dir = self.home / "copias"
        with mock.patch.dict(os.environ, {"SystemRoot": str(system_root)}), \
                mock.patch.dict(sys.modules, {"winreg": registry}):
            self.script.register_protocol(str(base_dir))
        install_dir = base_dir / "_protocol"
        self.assertEqual(
            (install_dir / "OpenAutosaveFile.ps1").read_bytes(),
            (Path(self.script.__file__).parent / "OpenAutosaveFile.ps1").read_bytes(),
        )
        settings = json.loads((install_dir / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["base_dir"], str(base_dir))
        self.assertEqual(settings["notepad_path"], str(npp_dir / "notepad++.exe"))
        self.assertEqual(registry.CreateKey.call_args_list, [
            mock.call(registry.HKEY_CURRENT_USER, r"Software\Classes\npp-autosave"),
            mock.call(
                registry.HKEY_CURRENT_USER, r"Software\Classes\npp-autosave\shell\open\command"
            ),
        ])
        command = registry.SetValueEx.call_args_list[-1].args[-1]
        self.assertIn('"' + str(install_dir / "OpenAutosaveFile.ps1") + '"', command)
        self.assertTrue(command.endswith(' "%1"'))
        self.assertNotIn("-Command", command)


if __name__ == "__main__":
    unittest.main()
