# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║                     NPP AUTOSAVE v1.3.0                          ║
║         Intelligent autosave for Notepad++                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Author:  Rickard Längkvist                                      ║
║  License: MIT (free to use, modify and share)                    ║
║  GitHub:  https://github.com/rickard-langkvist/npp-autosave      ║
╠══════════════════════════════════════════════════════════════════╣
║  FEATURES:                                                       ║
║  - Saves active tab 10s after you stop typing                    ║
║  - Saves ALL tabs every 5 minutes                                ║
║  - Keeps one current external copy per open document             ║
║  - Original files remain unchanged and marked as modified        ║
║  - New files: names copies using their first-copy timestamp      ║
╠══════════════════════════════════════════════════════════════════╣
║  INSTALLATION:                                                   ║
║  1. Save to: %APPDATA%/Notepad++/plugins/config/                 ║
║              PythonScript/scripts/autosave.py                    ║
║  2. Plugins > PythonScript > Configuration > ATSTARTUP           ║
║  3. Restart Notepad++                                            ║
╚══════════════════════════════════════════════════════════════════╝
"""

__version__ = "1.3.0"
__author__ = u"Rickard Längkvist"
__license__ = "MIT"

from Npp import notepad, editor, console, NOTIFICATION, STATUSBARSECTION
import Npp
import ctypes
import binascii
import hashlib
import os
import io
import json
import sys
import time
from datetime import datetime

text_type = type(u"")


def get_modified_notification():
    """Return the editor modification notification for this PythonScript version."""
    for owner_name in ("SCINTILLANOTIFICATION", "NOTIFICATION"):
        owner = getattr(Npp, owner_name, None)
        if owner is None:
            continue
        for attribute_name in ("MODIFIED", "SCN_MODIFIED"):
            notification = getattr(owner, attribute_name, None)
            if notification is not None:
                return notification
    raise AttributeError(
        "PythonScript no expone la notificación MODIFIED de Scintilla"
    )


try:
    MODIFIED_NOTIFICATION = get_modified_notification()
except AttributeError:
    MODIFIED_NOTIFICATION = None


try:
    from html import escape as _html_escape        # Python 3
except ImportError:
    from cgi import escape as _html_escape        # Python 2

try:
    from urllib.parse import quote as _url_quote   # Python 3
except ImportError:
    from urllib import quote as _url_quote         # Python 2


def escape_html(value):
    """Escape text so it can be inserted safely into HTML (attribute-safe)."""
    if value is None:
        return u""
    if not isinstance(value, type(u"")):
        value = u"{}".format(value)
    return _html_escape(value, quote=True)


def file_url(path):
    """Build a properly percent-encoded file:/// URL from a filesystem path."""
    p = u"{}".format(path).replace(u"\\", u"/")
    if not isinstance(p, bytes):
        p = p.encode("utf-8")
    # safe=":/" keeps the drive letter colon and slashes unencoded
    return u"file:///" + _url_quote(p, safe=":/")


def filesystem_text(path):
    """Keep filesystem bytes distinct from UTF-8 bytes returned by Npp."""
    if isinstance(path, bytes):
        return path.decode(sys.getfilesystemencoding())
    return path


def copy_url(path):
    """Address only a backup filename, never an executable or arbitrary path."""
    path = filesystem_text(path)
    directory = os.path.normcase(os.path.abspath(os.path.dirname(path)))
    folders = (
        (BACKUP_DIR, "backup"),
        (OLD_DIR, "old"),
    )
    for folder, bucket in folders:
        if directory == os.path.normcase(os.path.abspath(filesystem_text(folder))):
            name = os.path.basename(path).encode("utf-8")
            return u"npp-autosave:{}/{}".format(
                bucket, binascii.hexlify(name).decode("ascii")
            )
    raise ValueError(u"La ruta no es una copia de Autosave: {}".format(path))


# ══════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════
CONFIG_DIR = os.path.expanduser("~/Documents/NPP")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.txt")
DEFAULT_BASE_DIR = CONFIG_DIR


def get_configured_base_dir():
    """Read the base directory before the remaining settings are available."""
    configured_path = DEFAULT_BASE_DIR
    try:
        if os.path.exists(CONFIG_FILE):
            with io.open(CONFIG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key.strip().lower() == "base_dir":
                        configured_path = value.strip().strip(u"'\"")
                        break
    except Exception:
        configured_path = DEFAULT_BASE_DIR

    configured_path = os.path.expandvars(os.path.expanduser(configured_path))
    if not os.path.isabs(configured_path):
        configured_path = os.path.join(CONFIG_DIR, configured_path)
    return os.path.normpath(configured_path)


BASE_DIR = get_configured_base_dir()
BACKUP_DIR = os.path.join(BASE_DIR, "_backup")
OLD_DIR = os.path.join(BASE_DIR, "_old")
META_DIR = os.path.join(BASE_DIR, "_meta")
LOG_FILE = os.path.join(BASE_DIR, "autosave.log")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
STATS_FILE = os.path.join(META_DIR, "stats.json")

DEFAULT_CONFIG = {
    "idle_time": 10,
    "interval_time": 300,
    "base_dir": DEFAULT_BASE_DIR,
    "show_statusbar": True,
    "theme": "dark"
}


# ══════════════════════════════════════════════════════════════════
# INITIALIZATION
# ══════════════════════════════════════════════════════════════════
def init_folders():
    """Create necessary folders."""
    for d in [CONFIG_DIR, BASE_DIR, BACKUP_DIR, OLD_DIR, META_DIR]:
        if not os.path.exists(d):
            try:
                os.makedirs(d)
            except Exception as e:
                console.write(u"No se pudo crear el directorio {}: {}\n".format(d, e))

init_folders()


# ══════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════
def log(message, level="INFO"):
    """Write to log file and console."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = u"[{}] [{}] {}".format(timestamp, level, message)
        
        try:
            with io.open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry + u"\n")
        except Exception:
            pass
        
        try:
            console.write(entry.encode("utf-8") + "\n")
        except Exception:
            try:
                console.write(str(entry) + "\n")
            except Exception:
                pass
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════
def create_default_config():
    """Create default config file."""
    try:
        with io.open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(u"# ══════════════════════════════════════════════════════════\n")
            f.write(u"# Configuración de NPP Autosave v{}\n".format(__version__))
            f.write(u"# © {} {}\n".format(datetime.now().year, __author__))
            f.write(u"# ══════════════════════════════════════════════════════════\n\n")
            f.write(u"# Segundos desde la última edición para copiar la pestaña activa\n")
            f.write(u"idle_time = {}\n\n".format(DEFAULT_CONFIG["idle_time"]))
            f.write(u"# Segundos entre copias de TODAS las pestañas (300 = 5 minutos)\n")
            f.write(u"interval_time = {}\n\n".format(DEFAULT_CONFIG["interval_time"]))
            f.write(u"# Directorio base para copias, registro, índice y estadísticas\n")
            f.write(u"base_dir = {}\n\n".format(DEFAULT_CONFIG["base_dir"]))
            f.write(u"# Mostrar el estado en la barra de estado (true/false)\n")
            f.write(u"show_statusbar = {}\n\n".format(str(DEFAULT_CONFIG["show_statusbar"]).lower()))
            f.write(u"# Tema de index.html (dark/light)\n")
            f.write(u"theme = {}\n".format(DEFAULT_CONFIG["theme"]))
        log(u"Configuración creada: {}".format(CONFIG_FILE))
    except Exception as e:
        log(u"No se pudo crear la configuración: {}".format(e), "ERROR")


def get_config_value(key, default=None):
    """Read value from config."""
    if default is None:
        default = DEFAULT_CONFIG.get(key)
    
    try:
        if not os.path.exists(CONFIG_FILE):
            create_default_config()
            return default
        
        with io.open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                
                k, v = line.split("=", 1)
                k = k.strip().lower()
                v = v.strip()
                
                if k == key.lower():
                    if v.lower() in ("true", "1", "yes", "on"):
                        return True
                    elif v.lower() in ("false", "0", "no", "off"):
                        return False
                    elif v.lower() in ("dark", "light"):
                        return v.lower()
                    try:
                        return int(v)
                    except ValueError:
                        return v
    except Exception:
        pass
    return default


def get_idle_time():
    """Get idle time setting."""
    return max(1, get_config_value("idle_time", DEFAULT_CONFIG["idle_time"]))


def get_interval_time():
    """Get interval time setting."""
    return max(60, get_config_value("interval_time", DEFAULT_CONFIG["interval_time"]))


# ══════════════════════════════════════════════════════════════════
# STATUSBAR
# ══════════════════════════════════════════════════════════════════
last_save_time = None
last_save_result = None

def update_statusbar(message):
    """Update Notepad++ statusbar."""
    if not get_config_value("show_statusbar", True):
        return
    try:
        notepad.setStatusBar(STATUSBARSECTION.DOCTYPE, message)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# FILENAME HANDLING
# ══════════════════════════════════════════════════════════════════
def sanitize_filename(name):
    """Remove invalid characters from filename."""
    if not name:
        return ""
    
    invalid = '<>:"/\\|?*\r\n\t'
    for ch in invalid:
        name = name.replace(ch, "_")
    
    name = name.strip(". ")
    
    if len(name) > 80:
        name = name[:80]
    
    return name


def get_document_name(text, index):
    """Get document name from line 1."""
    if not text:
        return u"untitled_{}".format(index)
    
    first_line = text.split("\n", 1)[0].strip()
    name = sanitize_filename(first_line)
    
    if not name:
        return u"untitled_{}".format(index)
    
    return name


def is_file_saved(filepath):
    """Check if buffer has a real path on disk (not a new/untitled buffer).

    Notepad++ returns an absolute path (e.g. "C:\\...") for files that have
    been saved once, and a short relative name ("new 1") for untitled buffers.
    Using os.path.isabs() instead of os.path.exists() means that if a file is
    deleted or moved while it is open, autosave keeps using that path as the
    stable identity of the backup. It never recreates or changes the original.
    """
    if not filepath:
        return False

    return os.path.isabs(filepath)


# ══════════════════════════════════════════════════════════════════
# STATISTICS
# ══════════════════════════════════════════════════════════════════
def load_stats():
    """Load statistics from file."""
    try:
        if os.path.exists(STATS_FILE):
            with io.open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    
    return {
        "total_saves": 0,
        "total_bytes_saved": 0,
        "first_save": None,
        "last_save": None,
        "saves_per_day": {}
    }


def save_stats(stats):
    """Save statistics to file."""
    try:
        content = json.dumps(stats, ensure_ascii=False, indent=2)
        if not isinstance(content, text_type):
            content = content.decode("utf-8")
        with io.open(STATS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        log(u"No se pudieron guardar las estadísticas: {}".format(e), "ERROR")


def update_stats(filename, size):
    """Update statistics after save."""
    try:
        stats = load_stats()
        
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        stats["total_saves"] += 1
        stats["total_bytes_saved"] += size
        stats["last_save"] = now.isoformat()
        
        if not stats["first_save"]:
            stats["first_save"] = now.isoformat()
        
        if today not in stats["saves_per_day"]:
            stats["saves_per_day"][today] = 0
        stats["saves_per_day"][today] += 1
        
        save_stats(stats)
        
    except Exception as e:
        log(u"No se pudieron actualizar las estadísticas: {}".format(e), "ERROR")


# ══════════════════════════════════════════════════════════════════
# BACKUP MANAGEMENT
# ══════════════════════════════════════════════════════════════════
# Stable copy path -> content hash
_copy_state = {}
_untitled_copy_names = {}
MAX_SEARCH_CHARS_PER_FILE = 500000


def load_copy_metadata(copy_path):
    """Load metadata associated with an external copy."""
    metadata_path = copy_path + ".meta.json"
    if not os.path.exists(metadata_path):
        return {}
    try:
        with io.open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(u"No se pudieron leer los metadatos de {}: {}".format(copy_path, e), "WARNING")
        return {}


def write_copy_metadata(copy_path, text, source_path=None, source_name=None,
                        source_type="file", buffer_id=None):
    """Write metadata beside a copy without altering its contents."""
    metadata_path = copy_path + ".meta.json"
    previous = load_copy_metadata(copy_path)
    now = datetime.now().isoformat()
    encoded_text = text.encode("utf-8")

    created_at = previous.get("created_at")
    if not created_at and os.path.exists(copy_path):
        created_at = datetime.fromtimestamp(os.path.getctime(copy_path)).isoformat()
    if not created_at:
        created_at = now

    original_modified_at = None
    if source_path and os.path.exists(source_path):
        original_modified_at = datetime.fromtimestamp(
            os.path.getmtime(source_path)
        ).isoformat()

    metadata = {
        "schema_version": 1,
        "source_type": source_type,
        "original_path": source_path,
        "original_name": source_name,
        "source_extension": os.path.splitext(source_name or copy_path)[1].lower(),
        "buffer_id": buffer_id,
        "copy_name": os.path.basename(copy_path),
        "copy_path": os.path.abspath(copy_path),
        "created_at": created_at,
        "updated_at": now,
        "original_modified_at": original_modified_at,
        "copy_count": int(previous.get("copy_count", 0)) + 1,
        "size_bytes": len(encoded_text),
        "character_count": len(text),
        "line_count": len(text.splitlines()) if text else 0,
        "encoding": "utf-8",
        "sha256": hashlib.sha256(encoded_text).hexdigest()
    }

    content = json.dumps(metadata, ensure_ascii=False, indent=2)
    if not isinstance(content, text_type):
        content = content.decode("utf-8")
    with io.open(metadata_path, "w", encoding="utf-8") as f:
        f.write(content)


def save_external_copy(directory, name, text, extension=u".txt", force=False,
                       source_path=None, source_name=None, source_type="file",
                       buffer_id=None):
    """Create or update the single current external copy for a document."""
    try:
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()
        copy_path = os.path.join(directory, name + extension)

        if not force and _copy_state.get(copy_path) == digest:
            return None

        with io.open(copy_path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

        try:
            write_copy_metadata(
                copy_path, text, source_path, source_name, source_type, buffer_id
            )
        except Exception as e:
            log(
                u"La copia se creó, pero no se pudieron guardar sus metadatos: {}".format(e),
                "ERROR"
            )

        _copy_state[copy_path] = digest
        return True

    except Exception as e:
        log(u"Error al crear la copia externa: {}".format(e), "ERROR")
        return False


def get_backup_name(filepath, fallback_name):
    """Build a readable, collision-resistant backup name."""
    identity = filepath or fallback_name
    normalized = os.path.normcase(os.path.normpath(identity))
    identity_hash = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    safe_name = sanitize_filename(fallback_name) or u"untitled"
    return u"{}_{}".format(safe_name, identity_hash)


def available_copy_name(directory, name, extension):
    """Avoid overwriting a copy or its metadata when allocating a name."""
    candidate = name
    suffix = 2
    while (os.path.lexists(os.path.join(directory, candidate + extension)) or
           os.path.lexists(os.path.join(directory, candidate + extension + ".meta.json"))):
        candidate = u"{}_{}".format(name, suffix)
        suffix += 1
    return candidate


def get_untitled_copy_name(buffer_id, text, index):
    """Keep one stable filename for each untitled buffer in this session."""
    if buffer_id not in _untitled_copy_names:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        identity = u"untitled-buffer-{}".format(buffer_id)
        name = get_backup_name(identity, timestamp)
        _untitled_copy_names[buffer_id] = available_copy_name(BACKUP_DIR, name, u".txt")
    return _untitled_copy_names[buffer_id]


# ══════════════════════════════════════════════════════════════════
# FILE OPERATIONS
# ══════════════════════════════════════════════════════════════════
def scan_files(directory):
    """Scan files in a directory."""
    files = []
    try:
        directory = filesystem_text(directory)
        if not os.path.exists(directory):
            return files
        
        show_all_files = os.path.abspath(directory) in (
            os.path.abspath(filesystem_text(BACKUP_DIR)),
            os.path.abspath(filesystem_text(OLD_DIR))
        )
        for filename in os.listdir(directory):
            if filename.endswith(".meta.json"):
                continue
            if not show_all_files and not filename.endswith(".txt"):
                continue
                
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue
            
            metadata = load_copy_metadata(filepath)
            search_content = u""
            search_truncated = False
            try:
                with io.open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    search_content = f.read(MAX_SEARCH_CHARS_PER_FILE + 1)
                search_truncated = len(search_content) > MAX_SEARCH_CHARS_PER_FILE
                search_content = search_content[:MAX_SEARCH_CHARS_PER_FILE]
            except Exception as e:
                log(u"No se pudo indexar el contenido de {}: {}".format(filepath, e), "WARNING")

            files.append({
                "name": filename,
                "path": filepath,
                "mtime": os.path.getmtime(filepath),
                "size": os.path.getsize(filepath),
                "metadata": metadata,
                "search_content": search_content,
                "search_truncated": search_truncated
            })
        
        files.sort(key=lambda x: -x["mtime"])
    except Exception as e:
        log(u"Error al examinar {}: {}".format(directory, e), "ERROR")
    
    return files


def format_size(bytes):
    """Format file size."""
    if bytes < 1024:
        return "{} B".format(bytes)
    elif bytes < 1024 * 1024:
        return "{:.1f} KB".format(bytes / 1024.0)
    else:
        return "{:.1f} MB".format(bytes / (1024.0 * 1024.0))


def format_time_ago(timestamp):
    """Format time ago."""
    diff = time.time() - timestamp
    
    if diff < 60:
        return "ahora"
    elif diff < 3600:
        return "hace {} min".format(int(diff / 60))
    elif diff < 86400:
        return "hace {} h".format(int(diff / 3600))
    elif diff < 604800:
        return "hace {} días".format(int(diff / 86400))
    else:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


# ══════════════════════════════════════════════════════════════════
# HTML INDEX GENERATOR
# ══════════════════════════════════════════════════════════════════
def generate_index():
    """Generate HTML index file."""
    try:
        backup_files = scan_files(BACKUP_DIR)
        old_files = scan_files(OLD_DIR)
        
        stats = load_stats()
        total_size = sum(f["size"] for f in backup_files + old_files)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cutoff_7days = time.time() - (7 * 86400)
        recent_files = [f for f in backup_files if f["mtime"] > cutoff_7days]
        largest_file = max(backup_files, key=lambda x: x["size"]) if backup_files else None
        
        avg_per_day = 0
        if stats.get("saves_per_day"):
            avg_per_day = sum(stats["saves_per_day"].values()) / max(1, len(stats["saves_per_day"]))
        
        theme = get_config_value("theme", "dark")
        body_class = "light-mode" if theme == "light" else ""
        
        html = generate_html_content(
            [], backup_files, old_files,
            stats, total_size, now, len(recent_files),
            largest_file, avg_per_day, body_class
        )
        
        with io.open(INDEX_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        
    except Exception as e:
        log(u"Error al generar el índice: {}".format(e), "ERROR")


def generate_html_content(main_files, backup_files, old_files, stats, total_size, now, recent_count, largest_file, avg_per_day, body_class):
    """Generate complete HTML content."""
    
    def file_rows(files):
        rows = u""
        for f in files:
            url = escape_html(copy_url(f["path"]))
            date = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
            ago = format_time_ago(f["mtime"])
            size = format_size(f["size"])
            name = escape_html(f["name"])
            metadata = f.get("metadata") or {}
            original_path = metadata.get("original_path") or ""
            original_name = metadata.get("original_name") or ""
            created_at = metadata.get("created_at") or ""
            updated_at = metadata.get("updated_at") or ""
            extension = metadata.get("source_extension") or os.path.splitext(original_name or f["name"])[1]
            search_content = f.get("search_content") or u""
            truncated_note = u" (contenido indexado hasta 500.000 caracteres)" if f.get("search_truncated") else u""
            details = u"Origen: {} | Primera copia: {} | Última actualización: {}".format(
                original_path or original_name or f["name"],
                created_at or date,
                updated_at or date
            ) + truncated_note
            details = escape_html(details)
            
            rows += u'''
                <tr class="file-row"
                    data-name="{}"
                    data-path="{}"
                    data-extension="{}"
                    data-date="{}"
                    data-content="{}"
                    title="{}">
                    <td>
                        <a href="{}" class="file-link">{}</a>
                        <div class="match-snippet" hidden></div>
                    </td>
                    <td class="size">{}</td>
                    <td class="date" title="{}">{}</td>
                </tr>'''.format(
                    escape_html(u"{} {}".format(f["name"], original_name)),
                    escape_html(original_path),
                    escape_html(extension),
                    escape_html((updated_at or date)[:10]),
                    escape_html(search_content),
                    details,
                    url,
                    name,
                    size,
                    date,
                    ago
                )
        return rows
    
    current_year = datetime.now().year
    
    html = u'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NPP Autosave v{version}</title>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: rgba(255,255,255,0.05);
            --text-primary: #eee;
            --text-secondary: #888;
            --accent: #4fc3f7;
            --border: #333;
        }}
        
        body.light-mode {{
            --bg-primary: #f5f7fa;
            --bg-secondary: #e8eef5;
            --bg-card: rgba(0,0,0,0.05);
            --text-primary: #333;
            --text-secondary: #666;
            --border: #ddd;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            padding: 20px;
            min-height: 100vh;
            transition: all 0.3s ease;
        }}
        
        .container {{ max-width: 900px; margin: 0 auto; }}
        
        header {{
            text-align: center;
            padding: 25px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 25px;
            position: relative;
        }}
        
        .logo {{ font-size: 2.5em; margin-bottom: 5px; }}
        h1 {{ color: var(--accent); font-size: 1.8em; margin-bottom: 5px; }}
        .version {{ color: var(--text-secondary); font-size: 0.85em; }}
        .updated {{ color: var(--text-secondary); font-size: 0.85em; margin-top: 5px; }}
        
        .theme-toggle {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 8px 15px;
            border-radius: 20px;
            color: var(--text-primary);
            cursor: pointer;
            font-size: 1.1em;
        }}
        
        .theme-toggle:hover {{ background: var(--accent); color: #000; }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            margin: 20px 0;
        }}
        
        .stat {{
            background: var(--bg-card);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid var(--border);
        }}
        
        .stat-num {{ font-size: 1.4em; color: var(--accent); font-weight: bold; }}
        .stat-label {{ font-size: 0.75em; color: var(--text-secondary); margin-top: 2px; }}
        
        .stats-panel {{
            background: var(--bg-card);
            border-radius: 10px;
            padding: 18px;
            margin: 20px 0;
            border: 1px solid var(--border);
        }}
        
        .stats-panel h3 {{ color: var(--accent); margin-bottom: 12px; font-size: 1em; }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }}
        
        .stats-item-label {{ color: var(--text-secondary); font-size: 0.8em; }}
        .stats-item-value {{ color: var(--text-primary); font-size: 1.1em; font-weight: 500; }}
        
        .search {{
            margin: 20px 0;
            position: relative;
        }}
        
        .search input {{
            width: 100%;
            padding: 12px 20px 12px 45px;
            border: 1px solid var(--border);
            border-radius: 25px;
            background: var(--bg-card);
            color: var(--text-primary);
            font-size: 1em;
        }}
        
        .search input:focus {{
            outline: none;
            border-color: var(--accent);
        }}
        
        .search::before {{
            content: "🔍";
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
        }}
        
        .section {{
            background: var(--bg-card);
            border-radius: 10px;
            margin-bottom: 15px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        
        .section-header {{
            padding: 12px 18px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .section-header:hover {{ background: rgba(255,255,255,0.05); }}
        .section-header.main {{ background: rgba(79,195,247,0.12); }}
        .section-header.backup {{ background: rgba(255,193,7,0.12); }}
        .section-header.old {{ background: rgba(158,158,158,0.12); }}
        
        .section-title {{ font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .section-count {{ background: rgba(255,255,255,0.15); padding: 2px 10px; border-radius: 10px; font-size: 0.8em; }}
        
        .toggle-icon {{ transition: transform 0.2s; font-size: 0.7em; }}
        .section-header.collapsed .toggle-icon {{ transform: rotate(-90deg); }}
        
        .section-content {{ display: none; padding: 8px 12px; }}
        .section-content.open {{ display: block; }}
        
        table {{ width: 100%; border-collapse: collapse; }}
        .file-row:hover {{ background: rgba(255,255,255,0.08); }}
        td {{ padding: 8px 6px; border-bottom: 1px solid var(--border); }}
        .file-row:last-child td {{ border-bottom: none; }}
        
        .file-link {{ color: var(--text-primary); text-decoration: none; }}
        .file-link:hover {{ color: var(--accent); text-decoration: underline; }}

        .match-snippet {{
            color: var(--text-secondary);
            font-size: 0.78em;
            line-height: 1.4;
            margin-top: 5px;
            max-width: 65vw;
            white-space: pre-wrap;
        }}
        .match-snippet mark {{
            background: #ffdf5d;
            color: #222;
            border-radius: 2px;
            padding: 0 2px;
        }}
        
        .size, .date {{ text-align: right; color: var(--text-secondary); font-size: 0.8em; white-space: nowrap; }}
        
        footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.8em;
            border-top: 1px solid var(--border);
            margin-top: 25px;
        }}
        
        footer a {{ color: var(--accent); text-decoration: none; }}
        footer a:hover {{ text-decoration: underline; }}
        
        .no-results {{ text-align: center; padding: 30px; color: var(--text-secondary); display: none; }}
        .empty-state {{ text-align: center; padding: 20px; color: var(--text-secondary); }}
    </style>
</head>
<body class="{body_class}">
    <div class="container">
        <header>
            <div class="logo">📁</div>
            <h1>NPP Autosave</h1>
            <div class="version">v{version}</div>
            <div class="updated">Actualizado: {now}</div>
            <button class="theme-toggle" onclick="toggleTheme()">🌓</button>
        </header>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-num">{backup_count}</div>
                <div class="stat-label">Copias</div>
            </div>
            <div class="stat">
                <div class="stat-num">{old_count}</div>
                <div class="stat-label">Archivo</div>
            </div>
            <div class="stat">
                <div class="stat-num">{total_size}</div>
                <div class="stat-label">Tamaño</div>
            </div>
            <div class="stat">
                <div class="stat-num">{total_saves}</div>
                <div class="stat-label">Copias realizadas</div>
            </div>
        </div>
        
        <div class="stats-panel">
            <h3>📊 Estadísticas</h3>
            <div class="stats-grid">
                <div>
                    <div class="stats-item-label">Últimos 7 días</div>
                    <div class="stats-item-value">{recent_count} archivos</div>
                </div>
                <div>
                    <div class="stats-item-label">Media diaria</div>
                    <div class="stats-item-value">{avg_per_day:.1f} copias</div>
                </div>
                <div>
                    <div class="stats-item-label">Archivo más grande</div>
                    <div class="stats-item-value">{largest_file}</div>
                </div>
                <div>
                    <div class="stats-item-label">Total copiado</div>
                    <div class="stats-item-value">{total_bytes_saved}</div>
                </div>
            </div>
        </div>
        
        <div class="search">
            <input type="text" id="search"
                   placeholder="Buscar texto, nombre o ruta... Ej.: contenido:factura ext:.txt desde:2026-01-01"
                   oninput="filterFiles()">
        </div>
        
        <main>
            <div class="section">
                <div class="section-header backup" onclick="toggleSection('backup')">
                    <span class="section-title">💾 Copias</span>
                    <span><span class="section-count">{backup_count}</span> <span class="toggle-icon">▼</span></span>
                </div>
                <div class="section-content open" id="content-backup">
                    {backup_content}
                </div>
            </div>
            
            <div class="section">
                <div class="section-header old collapsed" onclick="toggleSection('old')">
                    <span class="section-title">📦 Archivo</span>
                    <span><span class="section-count">{old_count}</span> <span class="toggle-icon">▼</span></span>
                </div>
                <div class="section-content" id="content-old">
                    {old_content}
                </div>
            </div>
        </main>
        
        <div class="no-results" id="no-results">😕 No se encontraron archivos</div>
        
        <footer>
            <a href="file:///{config}">⚙️ Configuración</a> |
            <a href="file:///{log}">📋 Registro</a> |
            <a href="file:///{folder}">📂 Abrir carpeta</a>
            <br><br>
            NPP Autosave v{version} &copy; {year} {author}
        </footer>
    </div>
    
    <script>
        function toggleTheme() {{
            document.body.classList.toggle('light-mode');
            localStorage.setItem('npp-theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
        }}
        
        (function() {{
            if (localStorage.getItem('npp-theme') === 'light') document.body.classList.add('light-mode');
        }})();
        
        function toggleSection(id) {{
            var header = event.currentTarget;
            var content = document.getElementById('content-' + id);
            header.classList.toggle('collapsed');
            content.classList.toggle('open');
        }}
        
        function normalizeSearch(value) {{
            return (value || '').toLowerCase();
        }}

        function escapeRegExp(value) {{
            var specialCharacters = String.fromCharCode(
                123, 125, 40, 41, 124, 91, 93, 92
            );
            var pattern = new RegExp(
                '[.*+?^$' + specialCharacters + ']',
                'g'
            );
            return value.replace(pattern, '\\\\$&');
        }}

        function parseQuery(query) {{
            var terms = [];
            var re = /(?:[^\\s"]+|"[^"]*")+/g;
            var pieces = query.match(re) || [];

            pieces.forEach(function(piece) {{
                var separator = piece.indexOf(':');
                if (separator > 0) {{
                    var key = normalizeSearch(piece.slice(0, separator));
                    var value = piece.slice(separator + 1).replace(/^"|"$/g, '');
                    if (['contenido', 'ruta', 'ext', 'nombre', 'desde', 'hasta'].indexOf(key) >= 0) {{
                        terms.push({{ key: key, value: normalizeSearch(value) }});
                        return;
                    }}
                }}
                terms.push({{ key: 'cualquiera', value: normalizeSearch(piece.replace(/^"|"$/g, '')) }});
            }});
            return terms;
        }}

        function showSnippet(row, queryTerms) {{
            var snippet = row.querySelector('.match-snippet');
            var content = row.getAttribute('data-content') || '';
            var normalizedContent = normalizeSearch(content);
            var contentTerms = queryTerms
                .filter(function(term) {{ return term.key === 'contenido' || term.key === 'cualquiera'; }})
                .map(function(term) {{ return term.value; }})
                .filter(Boolean);

            if (!contentTerms.length) {{
                snippet.hidden = true;
                snippet.textContent = '';
                return;
            }}

            var term = contentTerms.find(function(value) {{ return normalizedContent.indexOf(value) >= 0; }});
            if (!term) {{
                snippet.hidden = true;
                snippet.textContent = '';
                return;
            }}

            var position = normalizedContent.indexOf(term);
            var start = Math.max(0, position - 100);
            var end = Math.min(content.length, position + term.length + 180);
            var preview = (start > 0 ? '…' : '') + content.slice(start, end) + (end < content.length ? '…' : '');
            var escaped = preview
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            var escapedTerm = term
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            var regex = new RegExp('(' + escapeRegExp(escapedTerm) + ')', 'ig');
            snippet.innerHTML = escaped.replace(regex, '<mark>$1</mark>');
            snippet.hidden = false;
        }}

        function matchesTerm(row, term) {{
            if (!term.value) return true;
            var name = normalizeSearch(row.getAttribute('data-name'));
            var path = normalizeSearch(row.getAttribute('data-path'));
            var extension = normalizeSearch(row.getAttribute('data-extension'));
            var date = row.getAttribute('data-date') || '';
            var content = normalizeSearch(row.getAttribute('data-content'));

            if (term.key === 'contenido') return content.indexOf(term.value) >= 0;
            if (term.key === 'ruta') return path.indexOf(term.value) >= 0;
            if (term.key === 'ext') return extension.indexOf(term.value) >= 0;
            if (term.key === 'nombre') return name.indexOf(term.value) >= 0;
            if (term.key === 'desde') return date >= term.value;
            if (term.key === 'hasta') return date <= term.value;
            return name.indexOf(term.value) >= 0 ||
                path.indexOf(term.value) >= 0 ||
                content.indexOf(term.value) >= 0;
        }}

        function filterFiles() {{
            var q = document.getElementById('search').value;
            var terms = parseQuery(q);
            var rows = document.querySelectorAll('.file-row');
            var visible = 0;
            
            rows.forEach(function(row) {{
                var match = terms.every(function(term) {{ return matchesTerm(row, term); }});
                row.style.display = match ? '' : 'none';
                if (match) showSnippet(row, terms);
                else row.querySelector('.match-snippet').hidden = true;
                if (match) visible++;
            }});
            
            document.getElementById('no-results').style.display = (q && visible === 0) ? 'block' : 'none';
            
            if (q) {{
                document.querySelectorAll('.section-content').forEach(function(c) {{ c.classList.add('open'); }});
                document.querySelectorAll('.section-header').forEach(function(h) {{ h.classList.remove('collapsed'); }});
            }}
        }}
    </script>
</body>
</html>'''.format(
        version=__version__,
        author=__author__,
        year=current_year,
        now=now,
        body_class=body_class,
        main_count=len(main_files),
        backup_count=len(backup_files),
        old_count=len(old_files),
        total_size=format_size(total_size),
        total_saves=stats.get("total_saves", 0),
        recent_count=recent_count,
        avg_per_day=avg_per_day,
        largest_file=escape_html(largest_file["name"]) if largest_file else "N/D",
        total_bytes_saved=format_size(stats.get("total_bytes_saved", 0)),
        main_content=u"<table>{}</table>".format(file_rows(main_files)) if main_files else u'<div class="empty-state">Aún no hay documentos</div>',
        backup_content=u"<table>{}</table>".format(file_rows(backup_files)) if backup_files else u'<div class="empty-state">Aún no hay copias</div>',
        old_content=u"<table>{}</table>".format(file_rows(old_files)) if old_files else u'<div class="empty-state">Aún no hay archivos archivados</div>',
        config=escape_html(file_url(CONFIG_FILE)),
        log=escape_html(file_url(LOG_FILE)),
        folder=escape_html(file_url(BASE_DIR))
    )
    
    return html


# ══════════════════════════════════════════════════════════════════
# SAVE OPERATIONS
# ══════════════════════════════════════════════════════════════════
def save_buffer(buffer_id, index, force=False):
    """Save a specific buffer."""
    current_buffer = None
    
    try:
        current_buffer = notepad.getCurrentBufferID()
        
        # Switch to target buffer (API takes exactly ONE argument)
        notepad.activateBufferID(buffer_id)
        
        # Check if modified
        if not force and not editor.getModify():
            return False
        
        # Get current file path
        filepath = notepad.getCurrentFilename()
        
        # Get text
        text = editor.getText()
        
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        
        saved = is_file_saved(filepath)
        
        # An empty buffer is only skippable when it is a NEW (untitled) file.
        # Emptying an existing file is a valid edit that must be saved.
        if not force and not text and not saved:
            return False
        
        if saved:
            # Existing files are backup-only: never modify the original.
            filename = os.path.basename(filepath)
            name, extension = os.path.splitext(filename)
            backup_name = get_backup_name(filepath, name)
            copy_created = save_external_copy(
                BACKUP_DIR, backup_name, text, extension or u".txt", force=force,
                source_path=filepath, source_name=filename,
                source_type="file", buffer_id=buffer_id
            )
            if copy_created is False:
                return False

            if copy_created:
                update_stats(os.path.basename(filepath), len(text))
                log(u"Copia externa actualizada (el original no se modificó): {}".format(filepath))
            
        else:
            # ═══ NEW FILE: Save using its first-copy timestamp ═══
            copy_name = get_untitled_copy_name(buffer_id, text, index)
            copy_created = save_external_copy(
                BACKUP_DIR, copy_name, text, force=force,
                source_name=get_document_name(text, index),
                source_type="untitled_buffer", buffer_id=buffer_id
            )
            if copy_created is False:
                return False
            
            filename = copy_name + u".txt"
            if copy_created:
                update_stats(filename, len(text))
                log(u"Copia externa actualizada (el búfer sigue modificado): {}".format(filename))
        
        return True
        
    except Exception as e:
        log(u"Error al copiar el búfer {}: {}".format(index, e), "ERROR")
        return False
        
    finally:
        # Switch back to original buffer
        try:
            if current_buffer is not None and current_buffer != buffer_id:
                notepad.activateBufferID(current_buffer)
        except Exception:
            pass


def save_current_buffer():
    """Save current/active buffer only."""
    global last_save_time, last_save_result
    
    try:
        if not editor.getModify():
            last_save_result = "unchanged"
            return False
        
        # Get current file path
        filepath = notepad.getCurrentFilename()
        
        # Get text
        text = editor.getText()
        
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        
        saved = is_file_saved(filepath)
        
        # An empty buffer is only skippable when it is a NEW (untitled) file.
        # Emptying an existing file is a valid edit that must be saved.
        if not text and not saved:
            last_save_result = "empty"
            return False
        
        if saved:
            # Existing files are backup-only: never modify the original.
            filename = os.path.basename(filepath)
            name, extension = os.path.splitext(filename)
            backup_name = get_backup_name(filepath, name)
            copy_created = save_external_copy(
                BACKUP_DIR, backup_name, text, extension or u".txt",
                source_path=filepath, source_name=filename,
                source_type="file",
                buffer_id=notepad.getCurrentBufferID()
            )
            if copy_created is False:
                last_save_result = "write_error"
                return False

            if copy_created:
                update_stats(os.path.basename(filepath), len(text))
            
            last_save_time = datetime.now()
            update_statusbar(u"✓ Copia {}".format(last_save_time.strftime("%H:%M:%S")))
            if copy_created:
                log(u"Copia externa actualizada (el original no se modificó): {}".format(filepath))
            
        else:
            # ═══ NEW FILE: Save using its first-copy timestamp ═══
            buffer_id = notepad.getCurrentBufferID()
            files = notepad.getFiles()
            index = 0
            for i, f in enumerate(files):
                if len(f) >= 2 and f[1] == buffer_id:
                    index = i
                    break
            
            copy_name = get_untitled_copy_name(buffer_id, text, index)
            copy_created = save_external_copy(
                BACKUP_DIR, copy_name, text,
                source_name=get_document_name(text, index),
                source_type="untitled_buffer", buffer_id=buffer_id
            )
            if copy_created is False:
                last_save_result = "write_error"
                return False
            
            filename = copy_name + u".txt"
            if copy_created:
                update_stats(filename, len(text))
            
            last_save_time = datetime.now()
            update_statusbar(u"✓ Copia {}".format(last_save_time.strftime("%H:%M:%S")))
            if copy_created:
                log(u"Copia externa actualizada (el búfer sigue modificado): {}".format(filename))
        
        last_save_result = "updated" if copy_created else "same"
        return True
        
    except Exception as e:
        last_save_result = "write_error"
        log(u"Error al copiar: {}".format(e), "ERROR")
        update_statusbar(u"✗ Error al copiar")
        return False


def save_all_buffers(force=False):
    """Save ALL open buffers."""
    global last_save_time
    
    try:
        files = notepad.getFiles()
        if not files:
            return 0
        
        saved_count = 0
        
        for index, file_info in enumerate(files):
            if len(file_info) >= 2:
                buffer_id = file_info[1]
                if save_buffer(buffer_id, index, force=force):
                    saved_count += 1
        
        if saved_count > 0:
            last_save_time = datetime.now()
            update_statusbar(u"✓ Se procesaron {} pestañas {}".format(saved_count, last_save_time.strftime("%H:%M:%S")))
            log(u"Copia periódica: {} pestañas procesadas".format(saved_count))
            generate_index()
        
        return saved_count
        
    except Exception as e:
        log(u"Error al copiar todas las pestañas: {}".format(e), "ERROR")
        return 0


# ══════════════════════════════════════════════════════════════════
# MANUAL COMMANDS
# ══════════════════════════════════════════════════════════════════
def manual_save():
    """Manual save command - saves current tab."""
    if save_current_buffer():
        generate_index()
        if last_save_result == "same":
            message = u"La copia ya está actualizada. No hay cambios nuevos."
        else:
            message = u"✓ La copia externa se ha actualizado."
        log(message)
    else:
        if last_save_result == "unchanged":
            message = u"La pestaña no tiene cambios pendientes. Modifícala antes de crear la copia."
        elif last_save_result == "empty":
            message = u"La pestaña nueva está vacía. Escribe contenido antes de crear la copia."
        else:
            message = u"No se pudo crear la copia externa. Revisa autosave.log para ver el error."
        log(message, "ERROR" if last_save_result == "write_error" else "INFO")


def manual_save_all():
    """Manual save all command - saves all tabs."""
    count = save_all_buffers()
    if count > 0:
        log(u"✓ {} copias de seguridad procesadas.".format(count))
    else:
        log(u"No hay pestañas modificadas para copiar. Si esperabas una copia, revisa autosave.log.")


def manual_force_save_all():
    """Force an external copy of every open tab."""
    count = save_all_buffers(force=True)
    if count > 0:
        log(u"✓ Se forzó la copia de {} pestañas abiertas.".format(count))
    else:
        log(u"No se pudo copiar ninguna pestaña. Revisa autosave.log.", "ERROR")


def open_index():
    """Open index in browser."""
    import subprocess
    try:
        generate_index()
        subprocess.Popen(['start', '', INDEX_FILE], shell=True)
    except Exception as e:
        log(u"No se pudo abrir el índice: {}".format(e), "ERROR")


def open_config():
    """Open config in Notepad++."""
    if not os.path.exists(CONFIG_FILE):
        create_default_config()
    notepad.open(CONFIG_FILE)


def open_folder():
    """Open NPP folder in Explorer."""
    import subprocess
    try:
        subprocess.Popen(['explorer', BASE_DIR])
    except Exception as e:
        log(u"No se pudo abrir la carpeta: {}".format(e), "ERROR")


# ══════════════════════════════════════════════════════════════════
# AUTOSAVER CLASS (DUAL MODE)
# ══════════════════════════════════════════════════════════════════
class AutoSaver:
    """
    Dual-mode autosaver:
    1. Idle-based: Saves the edited tab N seconds after inactivity
    2. Interval-based: Saves ALL tabs every 5 minutes

    Timing is driven by a Win32 timer (user32.SetTimer) created on the
    Notepad++ main thread, so the callback runs on the UI thread and it
    is safe to call the Notepad++/Scintilla API from it. The previous
    implementation used threading.Timer (background threads), which is
    NOT thread-safe against Notepad++ and could crash or hang it.
    """

    TICK_MS = 500  # timer resolution in milliseconds

    def __init__(self):
        self.running = False
        self.timer_id = None
        self._timer_proc = None       # keeps the ctypes callback alive
        self.last_change = 0.0
        self.target_buffer = None     # buffer that was being edited
        self.pending_idle_save = False
        self.last_interval = 0.0

    def on_text_changed(self, args):
        """Called on the UI thread on every text change - schedules idle save."""
        if not self.running:
            return

        self.last_change = time.time()
        self.pending_idle_save = True

        # Remember WHICH buffer is being edited, so the idle save hits the
        # right tab even if the user switches away before the timer fires.
        try:
            self.target_buffer = notepad.getCurrentBufferID()
        except Exception:
            self.target_buffer = None

        update_statusbar(u"⏳ Copia en {} s...".format(get_idle_time()))
    
    def _buffer_index(self, buffer_id):
        """Find the tab index of a buffer (used for new-file naming)."""
        try:
            for i, f in enumerate(notepad.getFiles()):
                if len(f) >= 2 and f[1] == buffer_id:
                    return i
        except Exception:
            pass
        return 0

    def _do_idle_save(self):
        """Save the buffer that was being edited, not whatever tab is active now."""
        global last_save_time

        target = self.target_buffer
        try:
            current = notepad.getCurrentBufferID()
        except Exception:
            current = None

        if target is None or target == current:
            # Fast path: still on the same tab - no buffer switching needed
            return save_current_buffer()

        # The user switched away - save the original target buffer instead
        ok = save_buffer(target, self._buffer_index(target))
        if ok:
            last_save_time = datetime.now()
            update_statusbar(u"✓ Copia {}".format(last_save_time.strftime("%H:%M:%S")))
        return ok

    def tick(self, hwnd, msg, timer_id, ticks):
        """UI-thread timer callback (runs ~2x/second)."""
        try:
            if not self.running:
                return

            now = time.time()

            # ── Idle save: correct buffer, only after inactivity ──
            if self.pending_idle_save and (now - self.last_change) >= get_idle_time():
                self.pending_idle_save = False
                try:
                    if self._do_idle_save():
                        generate_index()
                except Exception as e:
                    log(u"Error en la copia por inactividad: {}".format(e), "ERROR")

            # ── Interval save: ALL tabs ──
            if (now - self.last_interval) >= get_interval_time():
                self.last_interval = now
                try:
                    save_all_buffers()
                except Exception as e:
                    log(u"Error en la copia periódica: {}".format(e), "ERROR")

        except Exception as e:
            log(u"Error en el temporizador de Autosave: {}".format(e), "ERROR")
    
    def start(self):
        """Start both idle and interval monitoring."""
        if self.running:
            return
        
        self.running = True
        
        try:
            if MODIFIED_NOTIFICATION is None:
                raise AttributeError(
                    "PythonScript no expone la notificación MODIFIED de Scintilla"
                )
            editor.callback(self.on_text_changed, [MODIFIED_NOTIFICATION])
        except Exception as e:
            log(u"Error al registrar la devolución de llamada: {}".format(e), "ERROR")

        # Win32 timer with NULL hwnd is associated with the calling thread
        # (the script runs on Notepad++'s main thread), so the callback is
        # invoked from the message loop ON THE UI THREAD - safe for the API.
        try:
            self._timer_proc = ctypes.WINFUNCTYPE(
                None, ctypes.c_void_p, ctypes.c_uint,
                ctypes.c_size_t, ctypes.c_uint
            )(self.tick)
            user32 = ctypes.windll.user32
            user32.SetTimer.restype = ctypes.c_size_t
            self.timer_id = user32.SetTimer(None, 0, self.TICK_MS, self._timer_proc)
            if not self.timer_id:
                raise RuntimeError("SetTimer devolvió 0")
        except Exception as e:
            self.timer_id = None
            log(u"Error al crear el temporizador: {}".format(e), "ERROR")

        try:
            self.last_interval = time.time()

            idle = get_idle_time()
            interval = get_interval_time()

            log(u"Autosave iniciado")
            log(u"  - Pestaña activa: tras {} s sin actividad".format(idle))
            log(u"  - Todas las pestañas: cada {} s ({} min)".format(interval, interval // 60))

            update_statusbar(u"✓ Autosave activo")

        except Exception as e:
            log(u"Error al iniciar Autosave: {}".format(e), "ERROR")

    def stop(self):
        """Stop all monitoring."""
        self.running = False
        
        try:
            if self.timer_id is not None:
                ctypes.windll.user32.KillTimer(None, self.timer_id)
                self.timer_id = None
            self._timer_proc = None

            if MODIFIED_NOTIFICATION is not None:
                editor.clearCallbacks([MODIFIED_NOTIFICATION])
            log(u"Autosave detenido")
            
        except Exception as e:
            log(u"Error al detener Autosave: {}".format(e), "ERROR")


# ══════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════
try:
    _autosaver.stop()
except NameError:
    pass
except Exception:
    pass

_autosaver = AutoSaver()
_autosaver.start()

generate_index()

log(u"═" * 60)
log(u"NPP Autosave v{} cargado".format(__version__))
log(u"© {} {}".format(datetime.now().year, __author__))
log(u"═" * 60)
log(u"Directorio:    {}".format(BASE_DIR))
log(u"Configuración: {}".format(CONFIG_FILE))
log(u"Inactividad:  {} s (pestaña activa)".format(get_idle_time()))
log(u"Intervalo:     {} s / {} min (todas las pestañas)".format(get_interval_time(), get_interval_time() // 60))
log(u"═" * 60)
log(u"Archivos originales → Solo se copian al directorio de respaldo")
log(u"Todas las copias     → Subdirectorio _backup del directorio base")
log(u"═" * 60)
log(u"Comandos de copia:")
log(u"  manual_save()            Copiar pestaña activa modificada")
log(u"  manual_save_all()        Copiar todas las pestañas modificadas")
log(u"  manual_force_save_all()  Forzar copia de todas las pestañas")
log(u"Comandos de apertura:")
log(u"  open_index()             Abrir índice HTML")
log(u"  open_config()            Abrir config.txt")
log(u"  open_folder()            Abrir directorio de copias")
log(u"═" * 60)
