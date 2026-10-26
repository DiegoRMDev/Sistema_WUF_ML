# WUF Predict - documentación de arquitectura

Este directorio convierte el avance académico y el prototipo navegable en una guía de implementación. El PDF es la fuente de requisitos, historias de usuario, modelo de datos y tecnologías; `../prototipo/` es referencia visual y de flujo. Para HU01, el Analista importa CSV manualmente como sustituto acordado de la extracción WUF. HU02 compara snapshots y deriva “Permanece / Salió del catálogo”; HU03 excluye las etiquetas indeterminadas sin modificar la exportación auditable. HU04 usa por ahora etiquetas demo para el árbol de consistencia y requiere verificaciones humanas antes de considerarlo validado. HU05 genera reportes desde las predicciones vigentes y conserva cada exportación para auditoría.

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
10. [HU04 — Consistencia del catálogo](15-hu04-consistencia.md): DecisionTreeClassifier, etiquetas demo, métricas, diagrama del árbol, permisos y persistencia.
11. [HU05 — Reporte semanal de priorización](16-hu05-reporte-priorizacion.md): flujo de datos, prioridades, vista, filtros, exportación, historial, permisos y límites actuales.
12. [Guía de las tablas de la base de datos](17-guia-tablas-base-datos.md): explicación sencilla de las 18 tablas del esquema vigente y de sus relaciones.

## Convenciones

- Los elementos marcados **Definido en el avance** proceden del PDF.
- Los elementos marcados **Decisión de implementación** son una propuesta para hacer ejecutable el diseño; deben conservarse trazables y revisarse si contradicen una definición formal posterior.
- El prototipo guía la estructura visual, la navegación y el flujo esperado; sus cifras y registros estáticos son de muestra. Los datos funcionales se consultan desde PostgreSQL.
- El backend obtiene la fecha de captura del nombre validado del CSV, calcula semana ISO y audita aparte el momento de importación.
- La salida del catálogo que HU02 deriva comparando snapshots es una etiqueta proxy y no confirma adopción real.
- `wuf_predict` y las bases anteriores se conservan. Para preparar la base limpia `wuf_predict_v5` desde pgAdmin, crea la base y ejecuta [`../backend/schema_wuf_predict_v4.sql`](../backend/schema_wuf_predict_v4.sql), que integra el esquema final HU01–HU04 y acepta solo la regla HU04 v2. El nombre v4 del archivo identifica la versión del esquema; no es el nombre de la base. No ejecutes migraciones sobre esa base nueva. Los archivos `upgrade_hu04_*.sql` son solo para bases existentes que necesiten conservar historial anterior; `upgrade_hu03_ml.sql` queda para bases v2/v3 antiguas. Los CSV de HU02/HU03 y las etiquetas HU04 son sintéticos; no representan adopciones ni verificaciones reales.

## Orden de lectura

Leer primero visión y alcance, luego modelo de datos y arquitectura. Implementar las historias en orden de dependencia indicado en `04-modulos-hu.md`; los criterios de HU09 son transversales.
