# -*- coding: utf-8 -*-
"""Register the Autosave file opener for this user and open the HTML index."""

from Npp import notepad
import io
import json
import os
import shutil
import subprocess
import sys
import webbrowser

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote


def npp_string(value):
    """PythonScript's Python 2 bindings accept UTF-8 bytes, not unicode."""
    if sys.version_info[0] == 2 and isinstance(value, type(u"")):
        return value.encode("utf-8")
    return value


def get_config_dir():
    path = os.path.expanduser("~/Documents/NPP")
    if isinstance(path, bytes):
        path = path.decode(sys.getfilesystemencoding())
    return path


def get_index_path():
    """Resolve the same bootstrap configuration used by Autosave.py."""
    config_dir = get_config_dir()
    config_path = os.path.join(config_dir, "config.txt")
    base_dir = config_dir
    if os.path.exists(config_path):
        with io.open(config_path, "r", encoding="utf-8") as config:
            for line in config:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip().lower() == "base_dir":
                    base_dir = value.strip().strip(u"'\"")
                    break
    base_dir = os.path.expandvars(os.path.expanduser(base_dir))
    if not os.path.isabs(base_dir):
        base_dir = os.path.join(config_dir, base_dir)
    return os.path.normpath(os.path.join(base_dir, "index.html"))


def register_protocol(base_dir):
    """Install a per-user handler without changing file associations."""
    try:
        import winreg
    except ImportError:
        import _winreg as winreg

    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OpenAutosaveFile.ps1")
    if not os.path.isfile(source):
        raise IOError(u"Falta OpenAutosaveFile.ps1 junto a OpenAutosaveIndex.py.")
    npp_dir = notepad.getNppDir()
    if isinstance(npp_dir, bytes):
        npp_dir = npp_dir.decode("utf-8")
    executable = os.path.join(npp_dir, "notepad++.exe")
    powershell = os.path.join(
        os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
    )
    for path in (executable, powershell):
        if not os.path.isfile(path):
            raise IOError(u"No existe el ejecutable necesario:\n{}".format(path))

    install_dir = os.path.join(get_config_dir(), "_protocol")
    if not os.path.isdir(install_dir):
        os.makedirs(install_dir)
    handler = os.path.join(install_dir, "OpenAutosaveFile.ps1")
    shutil.copyfile(source, handler)
    settings = json.dumps({
        "base_dir": os.path.abspath(base_dir),
        "notepad_path": executable,
    }, ensure_ascii=False)
    if not isinstance(settings, type(u"")):
        settings = settings.decode("utf-8")
    with io.open(os.path.join(install_dir, "settings.json"), "w", encoding="utf-8") as config:
        config.write(settings)

    command = subprocess.list2cmdline([
        powershell, "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "RemoteSigned", "-File", handler,
    ]) + ' "%1"'
    key_path = r"Software\Classes\npp-autosave"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, u"URL:NPP Autosave")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, u"")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)


def open_autosave_index():
    """Register the protocol before opening the existing index in a browser."""
    try:
        index_path = get_index_path()
        if not os.path.isfile(index_path):
            raise IOError(
                u"No existe el indice:\n{}\n\nEjecuta Autosave.py para generarlo.".format(
                    index_path
                )
            )
        register_protocol(os.path.dirname(index_path))
        url = "file:///" + quote(index_path.replace("\\", "/").encode("utf-8"), safe=":/")
        if not webbrowser.open(url):
            raise RuntimeError(u"No se pudo abrir el navegador para:\n{}".format(index_path))
        return True
    except (IOError, OSError, RuntimeError, UnicodeError) as error:
        notepad.messageBox(npp_string(u"{}".format(error)), "NPP Autosave - Indice")
        return False


if __name__ == "__main__":
    open_autosave_index()
