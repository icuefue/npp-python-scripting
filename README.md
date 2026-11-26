# NPP Autosave

Scripts para Notepad++ en Windows, ejecutados mediante el plugin PythonScript.
Crean copias externas de los documentos y permiten buscarlas en un índice web
y abrirlas en Notepad++.

## Scripts

| Script | Resumen | Documentación |
| --- | --- | --- |
| [Autosave.py](./scripts/Autosave/Autosave.py) | Crea copias de las pestañas y genera un índice HTML. No modifica los archivos originales. | [Autosave](./scripts/Autosave/README.md) |
| [OpenAutosaveIndex.py](./scripts/OpenAutosaveIndex/OpenAutosaveIndex.py) | Registra el protocolo y abre el índice de Autosave en el navegador. | [OpenAutosaveIndex](./scripts/OpenAutosaveIndex/README.md) |
| [OpenAutosaveFile.ps1](./scripts/OpenAutosaveIndex/OpenAutosaveFile.ps1) | Lanzador auxiliar que abre en Notepad++ las copias seleccionadas en el índice. | [OpenAutosaveIndex](./scripts/OpenAutosaveIndex/README.md) |

Cada componente está en su propia carpeta de `scripts/`, junto con su
documentación y los archivos que necesita. Consulta sus README para los
requisitos, la instalación y el uso.

## Desarrollo

Las [instrucciones de desarrollo](.github/instructions/desarrollo.instructions.md)
y el [registro de decisiones](.github/instructions/decisiones.instructions.md)
son compartidos por GitHub Copilot y Claude Code.

## Licencia y atribución

Distribuido bajo la [licencia MIT](./LICENSE). Copyright © 2026 icuefue.
El script conserva la atribución original a Rickard Längkvist.
