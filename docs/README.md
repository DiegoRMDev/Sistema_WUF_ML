# WUF Predict - documentación de arquitectura

Este directorio convierte el avance académico y el prototipo navegable en una guía de implementación. El PDF es la fuente de requisitos, historias de usuario, modelo de datos y tecnologías; `../prototipo/` es referencia visual y de flujo. Para HU01, el Analista importa CSV manualmente como sustituto acordado de la extracción WUF. Para HU02, RF03 y el prototipo guían la comparación temporal de snapshots y las etiquetas “Permanece / Salió del catálogo”. La documentación distingue lo implementado actualmente de los cambios de esquema/contrato pendientes para HU02.

## Documentos

1. [Visión, alcance y requisitos](01-vision-requisitos.md): objetivos, RF, HU, roles y trazabilidad.
2. [Arquitectura y decisiones](02-arquitectura.md): tres capas, componentes, flujos, API y estructura actual.
3. [Modelo de datos](03-modelo-datos.md): diccionario original, límites actuales y esquema v2 para HU02.
4. [Plan de implementación por HU](04-modulos-hu.md): módulos incrementales, dependencias y criterios verificables.
5. [Estándares de desarrollo y seguridad](05-estandares.md): prácticas de código, validación, configuración, UI y operación.
6. [HU01 — Implementación de recolección](10-hu01-recoleccion.md): componentes, endpoints, migración, configuración e inicio local.
7. [Guía de inicio local](11-inicio-local.md): requisitos, instalación de dependencias y pasos para arrancar backend y frontend en Windows.
8. [Pendiente HU02 — variación de CSV demo](12-pendiente-datos-demo-hu02.md): cambios temporales y de cantidad a preparar al construir Dataset Histórico.

## Convenciones

- Los elementos marcados **Definido en el avance** proceden del PDF.
- Los elementos marcados **Decisión de implementación** son una propuesta para hacer ejecutable el diseño; deben conservarse trazables y revisarse si contradicen una definición formal posterior.
- El prototipo guía la estructura visual, la navegación y el flujo esperado; sus cifras y registros estáticos son de muestra. Los datos funcionales se consultan desde PostgreSQL.
- El backend obtiene la fecha de captura del nombre validado del CSV, calcula semana ISO y audita aparte el momento de importación.
- La salida del catálogo que HU02 deriva comparando snapshots es una etiqueta proxy y no confirma adopción real.
- `wuf_predict` se conserva como base anterior; el backend reconoce también `wuf_predict_v2`. La variación futura de estados/cantidades de CSV está registrada como pendiente de HU02.

## Orden de lectura

Leer primero visión y alcance, luego modelo de datos y arquitectura. Implementar las historias en orden de dependencia indicado en `04-modulos-hu.md`; los criterios de HU09 son transversales.
