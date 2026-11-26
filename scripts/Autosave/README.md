# Autosave

[Autosave.py](./Autosave.py) crea copias externas del contenido de las pestañas
de Notepad++ mediante el plugin PythonScript y genera un índice HTML para
consultarlas.

**Las copias no sustituyen el guardado normal:** el script no modifica el
archivo original ni marca la pestaña como guardada. Guarda en Notepad++ cuando
quieras actualizar el original.

## Requisitos e instalación

Necesitas Windows, Notepad++ y el plugin **PythonScript** con Python 2.7 o una
edición compatible con Python 3.

1. En Notepad++, abre **Plugins > Plugins Admin**, instala **PythonScript** y
   reinicia Notepad++.
2. Copia `Autosave.py` a la carpeta de scripts del usuario de PythonScript. Una
   ubicación habitual es:

   ```text
   %APPDATA%\Notepad++\plugins\config\PythonScript\scripts\
   ```

   La ruta puede variar según la instalación.
3. Ejecuta **Plugins > PythonScript > Scripts > Autosave**. El script inicia la
   supervisión y genera el índice. Abre **Plugins > PythonScript > Show
   Console** para comprobar los mensajes y consultar posibles errores.
4. Para ejecutarlo al arrancar Notepad++, establece **Initialisation** en
   **ATSTARTUP** en **Plugins > PythonScript > Configuration**. Añade estas
   líneas al `startup.py` del usuario de PythonScript:

   ```python
   import os
   import sys
   from Npp import notepad

   scripts_dir = os.path.join(notepad.getPluginConfigDir(), "PythonScript", "scripts")
   if scripts_dir not in sys.path:
       sys.path.insert(0, scripts_dir)
   import Autosave
   ```

   Si has instalado el script en otra carpeta, ajusta `scripts_dir`. Reinicia
   Notepad++ y comprueba la consola. `ATSTARTUP` inicia PythonScript; el código
   en `startup.py` carga Autosave.

Si no configuras el inicio automático, ejecuta Autosave manualmente en cada
sesión de Notepad++.

## Funcionamiento de las copias

- **Por inactividad:** tras una modificación y 10 segundos sin actividad, se
  copia la pestaña que se estaba editando, incluso si se ha cambiado de
  pestaña.
- **Periódica:** cada 300 segundos se procesan las pestañas modificadas.
- Ambos tiempos son configurables. Una pestaña nueva y vacía se omite en las
  copias normales; vaciar un archivo existente sí se considera un cambio.
- Las copias se escriben en `_backup`, tanto para archivos existentes como
  para pestañas nuevas. El contenido se guarda en UTF-8 y conserva los finales
  de línea y las líneas en blanco del editor.
- Para un archivo con ruta, el nombre de la copia incluye el nombre original,
  un identificador derivado de su ruta y su extensión. Si no tiene extensión,
  se usa `.txt`.
- Para una pestaña sin guardar, el nombre incluye la fecha y hora de su primera
  copia y un identificador; se usa un sufijo adicional si existe una colisión.
  El nombre se mantiene durante la sesión mientras ese búfer esté abierto.
- Las actualizaciones sobrescriben la copia actual: **no se mantiene un
  historial de versiones**. Las copias existentes no se renombran ni reparan
  automáticamente al iniciar el script.

Cada copia tiene un archivo `.meta.json` asociado con datos como su origen,
fechas, número de copias, tamaño y SHA-256. El índice no muestra estos
archivos de metadatos como documentos.

## Archivos y directorios

Por defecto, los datos se encuentran en `~/Documents/NPP`:

```text
~/Documents/NPP/
├── config.txt                   Configuración
├── index.html                   Índice para el navegador
├── autosave.log                 Registro de actividad y errores
├── _backup/                     Copias actuales y archivos .meta.json
├── _old/                        Archivos antiguos, si los hay
├── _meta/
│   └── stats.json               Estadísticas
└── _protocol/                   Instalado al ejecutar OpenAutosaveIndex
    ├── OpenAutosaveFile.ps1
    └── settings.json
```

`_old` se incluye en el índice para consultar archivos existentes, pero el
script no archiva allí automáticamente las copias actuales.

## Configuración

El archivo de configuración siempre está en `~/Documents/NPP/config.txt`.
Se crea con los valores predeterminados cuando Autosave lo necesita. Puedes
abrirlo con `open_config()` desde la consola.

```ini
# Segundos sin actividad antes de copiar la pestaña editada
idle_time = 10

# Segundos entre copias de las pestañas modificadas
interval_time = 300

# Directorio de datos; este ejemplo es el predeterminado
base_dir = ~/Documents/NPP

# Mensajes en la barra de estado
show_statusbar = true

# Tema inicial del índice: dark o light
theme = dark
```

`idle_time` tiene un mínimo de un segundo e `interval_time`, de 60 segundos.
`base_dir` admite rutas absolutas, `~`, variables de entorno y rutas relativas
al directorio que contiene `config.txt`. Las copias, el índice, el registro y
las estadísticas se guardan en ese directorio; `config.txt` y `_protocol`
permanecen en `~/Documents/NPP`.

Para cambiar `base_dir`, modifica `config.txt` y reinicia Notepad++ o vuelve a
cargar Autosave. Los archivos existentes no se mueven automáticamente.
Después, ejecuta de nuevo `OpenAutosaveIndex` para actualizar el registro del
protocolo. El botón del índice también permite cambiar el tema en el navegador.

## Índice HTML y búsqueda

El índice contiene las secciones **Copias** (`_backup`) y **Archivo** (`_old`),
además de estadísticas y enlaces a la configuración, el registro y la carpeta
de datos. Autosave genera el índice al arrancar y lo actualiza al procesar
copias; recarga la página del navegador para ver los cambios.

La búsqueda no distingue mayúsculas de minúsculas. Sin operador, busca en el
nombre, la ruta original y el contenido. Puedes combinar términos: todos deben
coincidir. Usa comillas para valores con espacios.

| Operador | Ejemplo | Busca en |
| --- | --- | --- |
| `contenido:` | `contenido:factura` | Contenido de la copia. |
| `nombre:` | `nombre:informe` | Nombre de la copia o nombre original. |
| `ruta:` | `ruta:"D:\Proyectos Cliente"` | Ruta original. |
| `ext:` | `ext:.py` | Extensión. |
| `desde:` | `desde:2026-11-01` | Fecha de actualización, inclusive. |
| `hasta:` | `hasta:2026-11-25` | Fecha de actualización, inclusive. |

Ejemplo combinado:

```text
contenido:error ruta:"C:\Proyecto" ext:.log desde:2026-11-01
```

Las fechas usan el formato `AAAA-MM-DD`. Cuando coincide el contenido, se
muestra un fragmento con el término resaltado. Se incluyen en el índice como
máximo los primeros 500.000 caracteres de cada archivo, por lo que la búsqueda
no encuentra texto situado después de ese límite. El índice contiene texto de
las copias: trátalo como información privada.

Para abrir las copias en Notepad++ desde el navegador, consulta
[OpenAutosaveIndex](../OpenAutosaveIndex/README.md).

## Comandos de consola

Abre **Plugins > PythonScript > Show Console**. Si has cargado el script
mediante `import Autosave` en `startup.py`, usa los comandos con el prefijo
`Autosave.`; por ejemplo, `Autosave.manual_save()`. Si lo ejecutaste desde el
menú de scripts, utiliza los nombres mostrados en la tabla.

| Comando | Función |
| --- | --- |
| `manual_save()` | Copia la pestaña activa si está modificada. |
| `manual_save_all()` | Procesa todas las pestañas modificadas. |
| `manual_force_save_all()` | Fuerza la copia de todas las pestañas abiertas, incluso las no modificadas o vacías. |
| `open_index()` | Regenera y abre el índice; no registra el protocolo. |
| `open_config()` | Abre `config.txt` en Notepad++. |
| `open_folder()` | Abre el directorio de datos en el Explorador. |
| `_autosaver.stop()` | Detiene la supervisión automática. |
| `_autosaver.start()` | Reinicia la supervisión automática. |

## Solución de problemas

- **Autosave no se inicia:** comprueba que PythonScript esté instalado, que
  `Autosave.py` esté en su carpeta de scripts y que `startup.py` y
  `ATSTARTUP` estén configurados si quieres iniciarlo automáticamente.
- **No aparece una copia:** verifica que la pestaña esté modificada, espera el
  tiempo configurado y revisa `autosave.log` y la consola de PythonScript.
  Comprueba también los permisos de escritura del directorio de datos.
- **Has cambiado `base_dir` y no ves los archivos antiguos:** las copias no se
  trasladan automáticamente. Revisa el directorio anterior y actualiza el
  registro del protocolo ejecutando `OpenAutosaveIndex` de nuevo.
