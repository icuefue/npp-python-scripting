# OpenAutosaveIndex

[OpenAutosaveIndex.py](./OpenAutosaveIndex.py) registra el protocolo de
apertura para el usuario actual y abre en el navegador el índice generado por
[Autosave](../Autosave/README.md).

[OpenAutosaveFile.ps1](./OpenAutosaveFile.ps1) es el lanzador auxiliar que
recibe los enlaces del índice y abre las copias en Notepad++.

## Requisitos e instalación

Necesitas Windows, Notepad++ con el plugin PythonScript, Windows PowerShell y
un índice generado previamente por Autosave. PythonScript puede usar Python
2.7 o una edición compatible con Python 3.

1. Copia `OpenAutosaveIndex.py` y `OpenAutosaveFile.ps1` **juntos** a la
   carpeta de scripts del usuario de PythonScript. Una ubicación habitual es:

   ```text
   %APPDATA%\Notepad++\plugins\config\PythonScript\scripts\
   ```

   La ruta puede variar según la instalación. El script busca el lanzador en
   su misma carpeta.
2. Ejecuta Autosave para generar el índice si aún no existe.
3. Ejecuta **Plugins > PythonScript > Scripts > OpenAutosaveIndex**.

No se necesita una instalación externa de Python ni un servidor.

## Abrir una copia en Notepad++

Busca un archivo en el índice abierto en el navegador y haz clic en su nombre.
Autoriza la apertura de la aplicación externa si se solicita.

Se abre **la copia**, no el archivo original. El lanzador utiliza el
`notepad++.exe` de la instalación que ejecutó `OpenAutosaveIndex`. Este script
abre el índice existente: no inicia Autosave ni regenera el índice.

El lanzador copia el script PowerShell y su configuración a
`~/Documents/NPP/_protocol` y registra `npp-autosave:` en
`HKEY_CURRENT_USER\Software\Classes`, sin necesidad de administrador ni
cambios en las asociaciones de archivos. Vuelve a ejecutar
`OpenAutosaveIndex` después de cambiar `base_dir`, mover Notepad++ o actualizar
`OpenAutosaveFile.ps1`.

Por seguridad, el manejador solo admite nombres de archivos directamente en
`_backup` o `_old`; rechaza rutas externas, metadatos, enlaces simbólicos,
uniones de directorios y tipos de enlace desconocidos. Admite marcadores de
archivos en la nube reconocidos, como los de OneDrive. Windows PowerShell se
ejecuta con la política `RemoteSigned` para ese proceso, sin cambiar la
política guardada del sistema. Los errores se muestran en un cuadro de diálogo.

Para eliminar el registro del protocolo, borra la clave
`HKEY_CURRENT_USER\Software\Classes\npp-autosave` del registro de Windows.
Después puedes eliminar `~/Documents/NPP/_protocol`; esto no elimina las
copias.

## Solución de problemas

- **El índice no existe:** ejecuta Autosave primero. `OpenAutosaveIndex` no lo
  genera por sí mismo.
- **El enlace no abre la copia:** vuelve a ejecutar `OpenAutosaveIndex`,
  comprueba que ambos archivos estén juntos y acepta la solicitud del
  navegador. Si una política de la organización bloquea PowerShell o los
  protocolos personalizados, consulta con el administrador.
