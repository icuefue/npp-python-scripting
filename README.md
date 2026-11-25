📁 NPP Autosave
Intelligent autosave plugin for Notepad++ that automatically saves your work.

Version
License
Python

✨ Features
Feature	Description
💾 Smart Saving	Copies active tab 10 seconds after you stop typing
🔄 Interval Backup	Copies ALL modified tabs every 5 minutes
📁 Backup Mode	Existing files → backup folder only, New files → NPP folder
📊 Statistics	Tracks saves, file sizes, and daily activity
🔍 HTML Index	Searchable file browser with dark/light theme
📦 Single Current Copy	One external file per open document; updates overwrite it
⚙️ Configurable	Simple config.txt for all settings
📥 Installation
Step 1: Install PythonScript Plugin
Open Notepad++
Go to Plugins → Plugins Admin
Search for PythonScript
Click Install
Restart Notepad++
Step 2: Download Script
Download autosave.py from Releases

Place it in:

text

%APPDATA%\Notepad++\plugins\config\PythonScript\scripts\
Step 3: Enable Autostart
Go to Plugins → PythonScript → Configuration
Find autosave.py in the list
Set Initialisation to ATSTARTUP
Click OK
Restart Notepad++
Step 4: Verify Installation
Open console: Plugins → PythonScript → Show Console

You should see:

text

════════════════════════════════════════════════════════════
NPP Autosave v1.2.0 loaded
© 2026 Rickard Längkvist
════════════════════════════════════════════════════════════
Folder:       C:\Users\YourName\Documents\NPP
Idle time:    10s (active tab)
Interval:     300s / 5min (all tabs)
════════════════════════════════════════════════════════════
📖 How It Works
Save Logic
text

┌─────────────────────────────────────────────────┐
│            FILE SAVE DECISION                   │
├─────────────────────────────────────────────────┤
│                                                 │
│   Does the file already have a path?            │
│                                                 │
│        YES                      NO              │
│         │                        │              │
│         ▼                        ▼              │
│   ┌───────────┐          ┌─────────────┐       │
│   │ Create    │          │ Save to     │       │
│   │ one copy  │          │ one copy in │       │
│   │ in backup │          │ backup      │       │
│   │           │          │ with date   │       │
│   └───────────┘          └─────────────┘       │
│         │                        │              │
│         └──────────┬─────────────┘              │
│                    ▼                            │
│            ┌─────────────┐                      │
│            │ Keep editor │                      │
│            │ modified    │                      │
│            └─────────────┘                      │
│                                                 │
└─────────────────────────────────────────────────┘
Two Save Modes
Mode	Trigger	Saves	Timing
Idle	Stop typing	Active tab	10 seconds
Interval	Timer	All tabs	Every 5 minutes
💡 Usage Examples
Example 1: New Document
Open new tab (Ctrl+N)
Type on line 1: My Notes
Type content below
Stop typing, wait 10 seconds
✅ Copy saved as: 2026-03-05_10-30-00_a1b2c3d4.txt
Example 2: Existing File
Open C:\Projects\readme.txt
Make changes
Stop typing, wait 10 seconds
✅ Original C:\Projects\readme.txt remains unchanged
✅ Current copy updated in ~/Documents/NPP/_backup/

The document stays marked as modified. Save manually in Notepad++ when you
want to update the original file.
Copies are UTF-8 and preserve the editor's exact line endings (CRLF, LF, CR,
or mixed) and intentional blank lines, without Windows newline translation.
📂 Folder Structure
text

C:\Users\YourName\Documents\NPP\
│
├── index.html                    ← Open in browser to view files
├── autosave.log                  ← Activity log
│
├── _backup/                      ← One current copy per open document
│   ├── 2026-03-05_10-30-00_a1b2c3d4.txt
│   ├── 2026-03-05_10-30-00_a1b2c3d4.txt.meta.json
│   ├── 2026-03-05_10-31-00_b2c3d4e5.txt
│   └── readme_e5f6a7b8.txt
│
│   Each copy has a .meta.json sidecar with source path/name, first-copy and
│   last-update timestamps, original modification time, copy count, byte/line
│   counts, extension, source type, and SHA-256.
│
├── _old/                         ← Legacy files from earlier versions
│
└── _meta/
    └── stats.json                ← Statistics data

Untitled copies use the date and time of their first copy and a collision
suffix; their name remains stable while the buffer is open. Copies of saved
files keep their original name and identity suffix. Existing copies are not
renamed or repaired on startup.
⚙️ Configuration
Edit the bootstrap configuration at:

```text
C:\Users\YourName\Documents\NPP\config.txt
```

`config.txt` remains at that fixed location so the script can find it before
knowing which data directory to use. All other files go to `base_dir`.

ini

# Base directory for external copies, log, index, and statistics
# Accepts absolute paths, ~, environment variables, or a path relative to
# the directory containing config.txt.
base_dir = D:\NPP-Autosave

# Seconds after typing stops to save active tab
idle_time = 10

# Seconds between saving ALL tabs (300 = 5 minutes)
interval_time = 300

# Show status in statusbar (true/false)
show_statusbar = true

# Theme for index.html (dark/light)
theme = dark
🎯 Console Commands
Open console: Plugins → PythonScript → Show Console

Command	Description
manual_save()	Create an external copy of the active tab
manual_save_all()	Create external copies of all modified tabs
manual_force_save_all()	Force an external copy of every open tab
open_index()	Open index in browser
open_config()	Open config file
open_folder()	Open NPP folder in Explorer
_autosaver.stop()	Stop autosave
_autosaver.start()	Restart autosave
📊 HTML Index
Open index.html in your browser to access:

🔍 Full-text search across file names, original paths, and copy contents
🔎 Search operators:
  - `contenido:factura`
  - `ruta:"D:\Proyectos Cliente"`
  - `nombre:informe`
  - `ext:.py`
  - `desde:2026-11-01`
  - `hasta:2026-11-25`
  - Combine filters, for example:
    `contenido:error ruta:"C:\Proyecto" ext:.log desde:2026-11-01`
🌓 Theme Toggle - Dark/Light mode
🔗 Quick Links - Click to open any file
📈 Statistics - View save activity
📁 Sections - Documents / Backups / Archive

Search previews show the matching content and highlight the first match. Up to
500,000 characters per file are embedded in the HTML index to keep it
manageable.

### Search in the browser, open copies in Notepad++

Preview HTML is no longer needed. Update [Autosave.py](./Autosave.py), then
place [OpenAutosaveIndex.py](./OpenAutosaveIndex.py) and
[OpenAutosaveFile.ps1](./OpenAutosaveFile.ps1) together in your PythonScript
scripts directory.

1. Restart Notepad++ (or reload Autosave) to regenerate the index with
   `npp-autosave:` links.
2. Run **Plugins > PythonScript > Scripts > OpenAutosaveIndex**.
3. Search in the default browser and click a filename. Allow the browser to
   open the external application when prompted.

The opener reads the same `config.txt` / `base_dir`. It installs a small
PowerShell handler and its settings in `~/Documents/NPP/_protocol` and registers
`HKEY_CURRENT_USER\Software\Classes\npp-autosave`. No administrator rights,
Preview HTML, external Python installation, or running server are required.
PythonScript's Python 2 and Python 3 editions are supported.

Each result opens the **backup copy**, not the original. Notepad++ handles
already-open files normally and is launched if it is closed. The handler uses
the executable of the Notepad++ installation that ran the opener. It accepts
only encoded filenames directly inside the configured `_backup` or `_old`
folder; path traversal, metadata sidecars, and symbolic links are rejected.
Windows cloud placeholders (including OneDrive) are allowed: their
`ReparsePoint` attribute is not, on its own, evidence of a symbolic link. The
handler checks the Windows reparse tag, allowing cloud placeholders while
rejecting symbolic links, junctions, and unrecognized reparse types.
Filenames are passed as a quoted argument, never as a shell command.

The opener registers the protocol before opening the existing index; it does
not restart Autosave or regenerate the HTML. Rerun it after changing `base_dir`
or moving Notepad++, and after updating `OpenAutosaveFile.ps1` so its installed
copy is refreshed. The `open_index()` console command still opens the browser
but does not perform protocol registration.

The handler uses Windows PowerShell with a process-local `RemoteSigned` policy;
it does not change the stored execution policy. If organizational policies
block PowerShell or custom protocols, ask your administrator rather than
disabling those policies. A console window may briefly appear when opening a
copy. Handler errors are shown in a dialog.

To uninstall the protocol, delete only
`HKEY_CURRENT_USER\Software\Classes\npp-autosave` in Registry Editor. The
`~/Documents/NPP/_protocol` folder can then be removed without deleting backups.

🐛 Troubleshooting
Script not loading
Check: Plugins → PythonScript → Configuration
Verify autosave.py is listed
Verify ATSTARTUP is selected
Restart Notepad++
Files not saving
Check folder permissions:

text

C:\Users\YourName\Documents\NPP\
Find your files
Run in console:

Python

open_folder()

Changing `base_dir` takes effect after restarting Notepad++ or reloading the
script. Existing files are not moved automatically.
📜 Changelog
Unreleased
✅ Existing files are copied to the backup folder without changing originals
✅ Backup names include a stable source identifier and preserve the extension
✅ Editor buffers remain marked as modified after backup
v1.2.0
✅ Dual save mode (original location vs NPP folder)
✅ Interval save for all tabs every 5 minutes
✅ Improved file detection
✅ Dynamic copyright year
v1.1.0
✅ Idle-based autosave
✅ HTML index with search
✅ Statistics tracking
✅ Dark/Light theme
✅ One current external copy per document
v1.0.0
✅ Initial release
📄 License
This project is licensed under the MIT License.

text

MIT License

Copyright (c) 2026 Rickard Längkvist

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
👤 Author
Rickard Längkvist

GitHub: @Tokke2
🔗 Links
📦 Repository
🐛 Issues
📥 Releases
⭐ Support
If you find this project useful, please give it a star!

Star

🤝 Contributing
Contributions are welcome!

Fork the project
Create your feature branch (git checkout -b feature/AmazingFeature)
Commit your changes (git commit -m 'Add some AmazingFeature')
Push to the branch (git push origin feature/AmazingFeature)
Open a Pull Request
