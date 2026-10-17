# Estándares de desarrollo, seguridad y experiencia

## Principios de ingeniería

- **SOLID:** separar responsabilidades (routers, casos de uso, dominio, adaptadores); depender de interfaces para BD, fuente CSV y almacenamiento de modelos; extender proveedores mediante adaptadores, no condicionales dispersos.
- **DRY:** centralizar reglas de roles, etiquetas, estados, errores, configuración y transformaciones. No duplicar límites de API y UI como si ambos fueran seguridad.
- **KISS:** preferir un backend modular y un pipeline reproducible antes que microservicios, colas o abstracciones sin necesidad demostrada.
- **YAGNI:** no construir administración genérica, integración CRM o personalización no requerida; resolver primero HU01-HU09.
- Funciones pequeñas con nombres de dominio claros; tipos/anotaciones; docstrings para contratos no obvios; comentarios explican por qué, no repiten el código.
- Evitar estado global mutable, consultas ORM en controladores y reglas de negocio en JavaScript. Un módulo posee sus reglas y expone servicio/contrato.

## Validación y manejo de errores

- Validar al borde de API con esquemas tipados: formato/tamaño, rangos, enum, fechas, parámetros de paginación y filtros; validar también invariantes y constraints en DB.
- Validar todo dato externo como no confiable: catálogo HTML, nombres, descripciones, URLs, CSV/XLSX/PDF importados y archivos descargados.
- Normalizar Unicode/espacios con cuidado; no transformar silenciosamente a un valor diferente. Rechazar o poner en cuarentena valores no reconocidos y contabilizarlos.
- Rechazar campos extra sensibles/no permitidos; limitar tamaño de payload, frecuencia y concurrencia de procesos costosos.
- Devolver errores JSON consistentes (`code`, mensaje seguro, identificador de solicitud); nunca devolver stacktrace, SQL, credenciales o contenido secreto.
- Logs estructurados con request/job ID, actor técnico, acción, resultado y duración; ocultar contraseñas, tokens, email/teléfono y texto sensible.

## Seguridad

- No copiar usuarios/contraseña de demo del prototipo a backend. Contraseñas con Argon2id/bcrypt mediante librería probada; respuestas de login no revelan si el email existe; limitación de intentos y recuperación segura.
- Sesión: elegir cookies HttpOnly, Secure, SameSite con protección CSRF si cookie; o tokens de corta vida con almacenamiento/rotación definidos. No confiar en rol almacenado en `sessionStorage`, encabezado enviado por cliente ni rol del formulario.
- Autorización por defecto denegada, validada en cada endpoint y también por registro/acción. Probar accesos permitidos y denegados; evitar IDOR/BOLA al descargar por ID.
- Secretos y DSN solo por entorno/gestor de secretos; validar variables requeridas al iniciar. `.env` ignorado en Git; `.env.example` con valores claramente ficticios; rotar secretos filtrados.
- Consultas parametrizadas/ORM; escapar salida HTML (`textContent`, no concatenar HTML sin sanitizar); CSP, CORS por allowlist, HTTPS; protección CSRF si aplica; límites de carga y descargas.
- CSV de captura: aceptar solo archivos del directorio configurado, validar tamaño/codificación/esquema, no permitir rutas de archivo enviadas por navegador y no confiar en valores importados. Si en el futuro se reactiva una fuente HTTP, aplicar allowlist HTTPS, timeout, límite de bytes y control de redirects para mitigar SSRF.
- CSV: neutralizar fórmulas iniciadas por `=`, `+`, `-`, `@` al exportar texto no confiable. Archivos: nombres generados, tipo validado, ubicación privada fuera de webroot y permiso antes de descargar.
- Minimización y retención: recolectar solo atributos necesarios; evitar adoptante/email/teléfono en el MVP predictivo; definir acceso, retención, borrado y backup protegido si se incorporan.
- Auditar cambios de configuración, activación de modelo, revisiones de alerta y acciones privilegiadas; guardar actor y antes/después sin copiar secretos.

## No hardcodear

- No hardcodear contraseñas, claves, URLs internas, DSN, destinatarios, umbrales, bandas de prioridad, horario, zona horaria, etiquetas, tamaño de página, límites operativos ni rutas de artefactos.
- Configuración validada desde variables de entorno/archivo local excluido o tabla de configuración autorizada. Umbrales versionados y con valores iniciales documentados; valor de ejemplo no implica valor aprobado.
- Persistir en DB reglas del negocio editables, con auditoría y validación de rango; credenciales siempre fuera de DB/config pública.
- Mantener constantes internas solo para valores inmutables del protocolo; centralizadas y explícitas.
- No usar nombres, SKU, contadores, métricas o contraseñas de ejemplo del prototipo en producción. No sustituir fallo de API por datos estáticos silenciosamente.

## UI, diseño y accesibilidad

- Mantener jerarquía visual del prototipo: marca WUF Predict, navegación lateral, topbar móvil, tarjetas y tablas; los tokens de color existentes en `prototipo/styles.css` son referencia inicial.
- Centralizar tokens CSS para fondos, superficies, borde, texto, prioridad y estados. Mantener consistencia entre claro/oscuro, contrastes WCAG AA para texto, no comunicar riesgo solo con color.
- Mobile first/responsive: menú navegable por teclado, tablas con scroll o presentación alternativa, formularios a una columna en móvil; sin overflow horizontal global.
- Usar elementos semánticos, label asociado a control, foco visible, orden de tabulación, `aria-live` para notificaciones y texto alternativo. Acciones con nombre accesible.
- Mostrar estados de carga, éxito, error, vacío, expiración de sesión y falta de permiso; confirmar operación destructiva; conservar filtros tras volver.
- Fechas visibles en zona acordada (prototipo sugiere Lima), almacenadas como instantes UTC/timestamptz cuando corresponda; formato localizado y explícito.
- Datos de dashboard y tablas vienen de API; mostrar fecha de actualización y etiqueta de modelo/regla para contextualizar probabilidades.

## Configuración y estructura

- Separar settings tipados por ambiente. Fallar temprano si falta secreto/config requerida; no registrar el objeto de configuración completo.
- Migraciones Alembic revisadas y reversibles cuando sea viable. Inicialización de demo solo en entorno local explícito.
- `.gitignore`: `.env*` con excepción de `.env.example`, DB locales, caches, exports con PII, modelos/artefactos y logs.
- Fijar versiones de dependencias; actualizar de forma controlada y preservar metadata del entorno ML. Modelos joblib son objetos ejecutables al cargar: aceptar solo artefactos internos firmados/inmutables, nunca uploads arbitrarios.

## Calidad y operación

El avance solicita registrar pruebas en HU09. Para cada HU, planificar unitarias de reglas/transformaciones, integración DB/API, autorización por rol, pruebas de contrato y verificaciones de UI/error/responsive. Probar reconstrucción y partición ML para evitar leakage, exportación segura, importes CSV incompletos y reintentos.

Mantener logs/health checks, backups restaurables de DB y artefactos, retención definida y runbook para fuente caída, modelo corrupto, migración fallida o job parcial. No promover un modelo sin métricas y versión de datos/código identificables. Agregar comentarios al codigo para una mejor legibilidad.