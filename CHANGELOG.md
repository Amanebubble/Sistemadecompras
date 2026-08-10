# Registro de Parches y Actualizaciones (CHANGELOG)

Este archivo mantiene un historial de todos los cambios, correcciones de errores (bugs) y nuevas características del Sistema de Compras Automatizado (SCA). 
Útil para mantener el contexto del programa y evitar alucinaciones en futuros desarrollos.

## [v1.9.1] - 2026-08-10
### Corregido
- **Timeout en Autenticación OAuth**: Se aumentó el tiempo de espera de la conexión temporalmente a 5 minutos (300s) cuando se lanza el navegador web para iniciar sesión en cuentas de Google. Así el usuario tiene tiempo suficiente para autorizar los permisos sin que el sistema aborte prematuramente por el timeout predeterminado de 15 segundos.
- **Generación de Reportes Confusa (30/60)**: Se deshabilitó el generador de reportes en segundo plano (`hilo_reportes`) del Orquestador Continuo. El programa mostraba un mensaje de "latido" cada 60 segundos que parecía indicar que estaba atascado ("30/60"). Ahora los reportes en Excel solo se generan estrictamente bajo demanda cuando el usuario presiona el botón de "Descargar", ahorrando CPU.
- **Bucle Infinito en IA**: Se añadió un bloque `try/except` envolviendo la llamada a la API de Groq en `extractor_pdf.py`. Ahora, si la IA devuelve un formato JSON erróneo o se produce un `KeyError`, el sistema envía el archivo a Revisión Manual y continúa, en lugar de atascarse en un bucle infinito de reintentos.
- **Timeout en Cuentas IMAP Grandes**: Se optimizó la función `listar_candidatos()` en `imap_connector.py`. Ahora utiliza `headers_only=True` para escanear solo los Asuntos y las Fechas de los correos en un 1 segundo, descargando los adjuntos pesados únicamente de los correos que pasan el filtro, previniendo errores de "Timeout" al conectar buzones nuevos con miles de correos.

## [v1.9.0] - 2026-08-10
### Añadido
- **Liberación Final (Release)**: Limpieza total de bases de datos, eliminación de entornos virtuales corruptos (`venv`), purga de cachés (`__pycache__`) y reestructuración de la documentación en el archivo `README.md` principal orientada a futuros desarrolladores (preparación para ERPNext).
- **Gestión Segura de Claves**: Refactorización del flujo de `.env`. Las contraseñas de las cuentas de correo (IMAP/OAuth) agregadas desde la Interfaz de Usuario web se inyectan dinámicamente y se guardan de forma segura, reduciendo la exposición en el código fuente.
