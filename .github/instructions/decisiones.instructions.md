---
applyTo: "**"
---

# Decisiones del repositorio

Estas decisiones son revisables. Antes de cambiarlas, explica al usuario la
propuesta y su impacto; registra aquí la decisión acordada y su justificación.
Para decisiones nuevas, anota el contexto, la decisión, el motivo y las
consecuencias. Distingue los motivos conocidos de los que no estén registrados.

## PythonScript con Python 2.7

- **Decisión:** desarrollar para Notepad++ y el plugin Python Script con
  Python 2.7, conservando la compatibilidad existente con Python 3.
- **Motivo:** Python 2.7 es la versión del plugin usada actualmente; los
  scripts también contemplan Python 3.
- **Consecuencia:** las pruebas con Python 3 no bastan para asegurar la
  compatibilidad con el entorno real.

## Copias externas, no guardado de originales

- **Decisión:** Autosave crea una copia actual por documento en `_backup` y
  no modifica el original ni marca el búfer como guardado.
- **Motivo:** mantener separada la copia automática del guardado explícito
  del usuario y evitar cambios no solicitados en el archivo original.
- **Consecuencia:** las actualizaciones sobrescriben la copia actual; no se
  ofrece un historial de versiones. El usuario debe guardar el original.

## Directorio base sin migración automática

- **Decisión:** `config.txt` y `_protocol` permanecen en `~/Documents/NPP`.
  Al cambiar `base_dir`, no se copian ni mueven automáticamente los datos
  anteriores.
- **Motivo:** se descartó una implementación de migración automática porque
  introducía demasiada complejidad para el cambio solicitado.
- **Consecuencia:** los datos anteriores permanecen en su ubicación y hay
  que volver a ejecutar `OpenAutosaveIndex` para actualizar el protocolo.

## No modificar copias antiguas al iniciar

- **Decisión:** no renombrar automáticamente copias antiguas ni incluir los
  comandos de reparación de finales de línea eliminados.
- **Motivo:** se confirmó que la eliminación de ambas funcionalidades era
  correcta; no consta una justificación más detallada.
- **Consecuencia:** las copias existentes se conservan sin migración ni
  reparación automática.

## Apertura de copias desde el índice

- **Decisión:** el índice usa un protocolo registrado para el usuario actual
  que abre las copias en Notepad++, no los archivos originales. El manejador
  limita los enlaces a archivos permitidos de `_backup` y `_old`.
- **Motivo:** permitir la búsqueda en el navegador y la apertura en el editor,
  sin convertir los enlaces en un mecanismo de apertura de rutas arbitrarias.
- **Consecuencia:** los cambios en el índice, el registro o el lanzador deben
  mantenerse coherentes y validar las restricciones de ruta existentes.
