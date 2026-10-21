# WUF Predict - documentación de arquitectura

Este directorio convierte el avance académico y el prototipo navegable en una guía de implementación. El PDF es la fuente de requisitos, historias de usuario, modelo de datos y tecnologías; `../prototipo/` es referencia visual y de flujo. Para HU01, el Analista importa CSV manualmente como sustituto acordado de la extracción WUF. HU02 compara snapshots y deriva “Permanece / Salió del catálogo”; HU03 excluye las etiquetas indeterminadas sin modificar la exportación auditable.

## Documentos

1. [Visión, alcance y requisitos](01-vision-requisitos.md): objetivos, RF, HU, roles y trazabilidad.
2. [Arquitectura y decisiones](02-arquitectura.md): tres capas, componentes, flujos, API y estructura actual.
3. [Modelo de datos](03-modelo-datos.md): diccionario original, límites actuales y esquema v2 para HU02.
4. [Plan de implementación por HU](04-modulos-hu.md): módulos incrementales, dependencias y criterios verificables.
5. [Estándares de desarrollo y seguridad](05-estandares.md): prácticas de código, validación, configuración, UI y operación.
6. [HU01 — Implementación de recolección](10-hu01-recoleccion.md): componentes, endpoints, migración, configuración e inicio local.
7. [Guía de inicio local](11-inicio-local.md): requisitos, instalación de dependencias y pasos para arrancar backend y frontend en Windows.
8. [HU02 — guía del Dataset Histórico](13-hu02-dataset-historico.md): reglas de cohorte, endpoints, interfaz, escenarios demo y tratamiento de filas indeterminadas.
9. [HU03 — Entrenamiento y predicción](14-hu03-entrenamiento-modelo.md): preparación de datos, Random Forest, métricas, artefactos, migración y uso de la interfaz.

## Convenciones

- Los elementos marcados **Definido en el avance** proceden del PDF.
- Los elementos marcados **Decisión de implementación** son una propuesta para hacer ejecutable el diseño; deben conservarse trazables y revisarse si contradicen una definición formal posterior.
- El prototipo guía la estructura visual, la navegación y el flujo esperado; sus cifras y registros estáticos son de muestra. Los datos funcionales se consultan desde PostgreSQL.
- El backend obtiene la fecha de captura del nombre validado del CSV, calcula semana ISO y audita aparte el momento de importación.
- La salida del catálogo que HU02 deriva comparando snapshots es una etiqueta proxy y no confirma adopción real.
- `wuf_predict` y `wuf_predict_v2` se conservan sin cambios; el esquema v2 puede instalarse en una base limpia `wuf_predict_v3`. Los CSV con transiciones controladas están en `data/capturas/escenario_hu02_v3/`; la variante variable (180→165→190), con salida gradual por `no_disponible`, está en `data/capturas/escenario_hu02_variable_v3/` y el usuario confirmó su prueba en una base demo aislada.

## Orden de lectura

Leer primero visión y alcance, luego modelo de datos y arquitectura. Implementar las historias en orden de dependencia indicado en `04-modulos-hu.md`; los criterios de HU09 son transversales.
