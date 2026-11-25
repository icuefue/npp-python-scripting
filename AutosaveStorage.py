# -*- coding: utf-8 -*-
"""Locate and migrate Autosave's data directory."""

import ctypes
import io
import os
import shutil
import sys
import tempfile


_script_dir = os.path.dirname(os.path.abspath(__file__))
if isinstance(_script_dir, bytes):
    _script_dir = _script_dir.decode(sys.getfilesystemencoding())
LOCATOR_FILE = os.path.join(_script_dir, u".autosave-base-dir")


def default_base_dir():
    return os.path.expanduser(u"~/Documents/NPP")


def active_base_dir():
    if not os.path.exists(LOCATOR_FILE):
        return default_base_dir()
    with io.open(LOCATOR_FILE, "r", encoding="utf-8") as source:
        path = source.read().strip()
    if not path or not os.path.isabs(path):
        raise ValueError(u"El localizador de Autosave no contiene una ruta absoluta válida.")
    if not os.path.isfile(os.path.join(path, "config.txt")):
        raise IOError(u"No existe la configuración del directorio activo: {}".format(path))
    return os.path.normpath(path)


def configured_base_dir(config_path):
    base = os.path.dirname(config_path)
    if not os.path.isfile(config_path):
        return base
    with io.open(config_path, "r", encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip().lower() == "base_dir":
                base = value.strip().strip(u"'\"")
                if not base:
                    raise ValueError(u"base_dir no puede estar vacío.")
                break
    base = os.path.expandvars(os.path.expanduser(base))
    if not os.path.isabs(base):
        base = os.path.join(os.path.dirname(config_path), base)
    return os.path.abspath(os.path.normpath(base))


def atomic_replace(source, destination):
    if os.name == "nt":
        move_file = ctypes.windll.kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        move_file.restype = ctypes.c_int
        if not move_file(source, destination, 0x9):
            raise ctypes.WinError()
    else:
        os.rename(source, destination)


def write_atomic(path, data):
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix=".autosave-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        atomic_replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)


def write_locator(base):
    write_atomic(LOCATOR_FILE, (os.path.abspath(base) + u"\n").encode("utf-8"))


def _same_path(first, second):
    return os.path.normcase(os.path.realpath(first)) == os.path.normcase(os.path.realpath(second))


def _validate_separate_directories(source, destination):
    first = os.path.normcase(os.path.realpath(source))
    second = os.path.normcase(os.path.realpath(destination))
    if first.startswith(second.rstrip(os.sep) + os.sep):
        raise ValueError(u"El destino no puede contener el directorio de origen.")


def _copy_file(source, destination):
    if os.path.islink(source) or os.path.islink(destination):
        raise ValueError(u"No se pueden migrar enlaces simbólicos: {}".format(source))
    directory = os.path.dirname(destination)
    fd, temporary = tempfile.mkstemp(prefix=".autosave-copy-", dir=directory)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        atomic_replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)


def _copy_tree(source, destination):
    if not os.path.isdir(source):
        raise IOError(u"No existe el directorio de origen: {}".format(source))
    _validate_separate_directories(source, destination)
    if not os.path.isdir(destination):
        os.makedirs(destination)
    def raise_walk_error(error):
        raise error

    for root, directories, files in os.walk(source, onerror=raise_walk_error):
        relative = os.path.relpath(root, source)
        target = destination if relative == "." else os.path.join(destination, relative)
        if os.path.islink(root) or os.path.islink(target):
            raise ValueError(u"No se pueden migrar directorios enlazados: {}".format(root))
        if not os.path.isdir(target):
            os.makedirs(target)
        for name in list(directories):
            if os.path.islink(os.path.join(root, name)) or os.path.islink(os.path.join(target, name)):
                raise ValueError(u"No se pueden migrar directorios enlazados: {}".format(name))
            if _same_path(os.path.join(root, name), destination):
                directories.remove(name)
                continue
        for name in files:
            _copy_file(os.path.join(root, name), os.path.join(target, name))


def _set_config_base(path, base):
    with io.open(path, "r", encoding="utf-8") as source:
        lines = source.readlines()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip().lower()
            if key == "base_dir":
                lines[index] = u"base_dir = {}\n".format(base)
                break
    else:
        if lines and not lines[-1].endswith((u"\n", u"\r")):
            lines[-1] += u"\n"
        lines.append(u"base_dir = {}\n".format(base))
    write_atomic(path, u"".join(lines).encode("utf-8"))


def prepare_storage(register_protocol):
    """Apply a pending directory change; retain the old directory on failure."""
    has_locator = os.path.exists(LOCATOR_FILE)
    old_base = active_base_dir()
    old_config = os.path.join(old_base, "config.txt")
    if not os.path.isfile(old_config):
        return old_base
    new_base = configured_base_dir(old_config)
    if _same_path(old_base, new_base):
        if not has_locator:
            write_locator(old_base)
        return old_base

    legacy = not has_locator
    if legacy:
        # Older versions kept configuration and the protocol outside base_dir.
        if not os.path.isdir(new_base):
            os.makedirs(new_base)
        _copy_file(old_config, os.path.join(new_base, "config.txt"))
        protocol = os.path.join(old_base, "_protocol")
        if os.path.isdir(protocol):
            _copy_tree(protocol, os.path.join(new_base, "_protocol"))
    else:
        _copy_tree(old_base, new_base)
    _set_config_base(os.path.join(new_base, "config.txt"), new_base)

    protocol_installed = os.path.isfile(os.path.join(old_base, "_protocol", "settings.json"))
    if protocol_installed:
        register_protocol(new_base)
    try:
        write_locator(new_base)
    except Exception:
        if protocol_installed:
            register_protocol(old_base)
        raise
    return new_base
