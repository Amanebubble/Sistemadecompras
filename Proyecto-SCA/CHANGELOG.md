# Registro de Cambios (Changelog) - Proyecto SCA

## [1.9] - 2024-05-XX
### Añadido
- **Consola Narrativa**: Se rediseñó completamente la salida de la consola de la Interfaz de Usuario para que sea descriptiva y narrada en lenguaje natural, ocultando las etiquetas técnicas internas (`[FASE:...]`, `[SEMAFORO:...]`).
- **Dashboard Estadístico en Vivo**: Se agregó una tabla dinámica en la interfaz principal (`index.html`) que reporta en tiempo real la cantidad de documentos descargados por cada cuenta de correo durante el ciclo activo.
- **Detección Dinámica de Cuentas**: El orquestador ahora recarga el archivo `accounts.json` al inicio de cada ciclo de descarga (Fase 1), permitiendo que el motor detecte y procese nuevas cuentas agregadas desde la interfaz sin necesidad de reiniciar el servicio principal.
- **Mejora en Tiempos de Timeout**: Se incrementó significativamente el tiempo de espera del socket durante la autenticación OAuth2 de Google para dar más margen al usuario de aceptar los permisos en el navegador.

### Modificado
- Se refactorizaron los módulos internos (`orquestador.py`, `enrutador.py`, `extractor_pdf.py`, `estandarizador.py`) para emitir mensajes unificados y narrativos dirigidos al usuario.
- El módulo `extractor_pdf` ahora utiliza prefijos como `[Inteligencia Artificial]` para indicar cuando la IA Groq está en uso, de forma que sea fácilmente identificable en la UI.
- Se ha desacoplado el motor de generación de reportes automáticos Beta (`hilo_reportes`) del ciclo principal de descargas para evitar bloqueos del pipeline.

### Notas para Programadores / Futuro
Esta versión (1.9) marca la finalización de los parches intensivos de estabilización del motor de correo y procesamiento de documentos DTE. El sistema está ahora listo para funcionar de manera estable y como un servicio de fondo en producción. En el futuro, la lógica central de validación y estandarización construida aquí servirá como base para la integración con un ERP completo (como ERPNext) y para el desarrollo del módulo de auditoría.
