---
applyTo: "**"
---

# Desarrollo

## Contexto y compatibilidad

- Este repositorio contiene scripts para **Notepad++ en Windows**, ejecutados
  mediante el plugin **Python Script** (PythonScript), no una aplicación
  Python independiente.
- La versión de Python usada actualmente por el plugin es **2.7**. Mantén
  compatibles con Python 2.7 la sintaxis, la biblioteca estándar y las APIs de
  los scripts que se ejecutan en el plugin. Conserva también la compatibilidad
  existente con Python 3; no elimines ninguna sin una decisión explícita.
- Respeta las diferencias entre texto Unicode y bytes de Python 2 y 3, las
  rutas de Windows y los finales de línea. No presupongas que el intérprete
  local es el mismo que usa PythonScript.
- Las APIs de Notepad++ y Scintilla deben ejecutarse en el hilo de la interfaz.
  No sustituyas el temporizador Win32 por llamadas a esas APIs desde hilos de
  trabajo.

## Forma de trabajar

- Crea una rama nueva `feature/<nombre-descriptivo>` para cada nueva
  funcionalidad. Para otros tipos de trabajo se admiten prefijos habituales
  de Gitflow, como `bugfix/`, `hotfix/` y `release/`.
- Integra las ramas en `main` mediante pull requests.
- Prioriza soluciones simples, claras y suficientes para el requisito. Evita
  abstracciones, dependencias, configuraciones y cambios de alcance que no
  sean necesarios.
- Lee el código y las decisiones relevantes antes de modificarlo; reutiliza
  los patrones existentes y preserva el comportamiento no afectado.
- **No refactorices código existente automáticamente.** Si una refactorización
  parece útil, explica al usuario por qué y solicita su aprobación antes de
  hacerla. Mantén los cambios requeridos por la tarea separados de mejoras
  opcionales.
- Trata los archivos del usuario y las copias con especial cuidado: no los
  sobrescribas, muevas o elimines fuera del comportamiento solicitado y
  confirmado. Comunica los errores; no los ocultes con resultados de éxito.
- En cada modificación, revisa si deben actualizarse el
  [README](../../README.md), estas instrucciones o el
  [registro de decisiones](decisiones.instructions.md), y actualízalos cuando
  corresponda. Si se toma o revisa una decisión, documenta el motivo y sus
  consecuencias; no inventes justificaciones desconocidas.

## Validación

- Añade pruebas centradas en el comportamiento nuevo o corregido. Ejecuta las
  pruebas relevantes y amplía la comprobación cuando el cambio lo requiera.
- Desde la raíz, las pruebas existentes con dobles de Notepad++ se ejecutan
  con **Python 3**:

  ```text
  python3 -m unittest discover -s tests -v
  ```

  En Windows, usa `py -3 -m unittest discover -s tests -v` si el lanzador
  `py` está disponible.

- Para el lanzador PowerShell, ejecuta en Windows:

  ```text
  powershell -NoProfile -File tests/test_autosave_protocol.ps1
  ```

  También puede ejecutarse con `pwsh` donde esté disponible; las pruebas
  simuladas no sustituyen la comprobación real en Windows.
- Cuando esté disponible Python 2.7, comprueba también la sintaxis de los
  scripts Python con `python2 -m py_compile Autosave.py OpenAutosaveIndex.py`.
  Verifica los cambios que dependan del plugin en Notepad++ con PythonScript
  2.7 cuando sea posible. Indica expresamente qué validaciones no se han
  podido ejecutar.
