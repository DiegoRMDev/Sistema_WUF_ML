# WUF Predict - documentación de arquitectura

Este directorio registra los requisitos de origen y describe la implementación actual, usando el prototipo como guía visual. El PDF es la fuente inicial de requisitos, historias de usuario, modelo de datos y tecnologías; `../prototipo/` guía lo visual y el flujo. Para HU01, el Analista importa CSV manualmente como sustituto acordado de la extracción WUF. HU02 compara snapshots y deriva “Permanece / Salió del catálogo”; HU03 entrena el Random Forest de OE1; HU04 usa etiquetas demo para el árbol de consistencia y requiere verificaciones humanas para una validación real; HU07 persiste la atención interna de alertas de HU04. HU06 aplica K-Means a todas las mascotas disponibles para descubrir segmentos y luego marca los perfiles con atributos desfavorecidos. HU05 entrega dos resultados separados: prioridad OE1 basada en el Random Forest y segmentos OE3 basados en K-Means; guarda cada exportación para auditoría.

## Documentos

1. [Visión, alcance y requisitos](01-vision-requisitos.md): objetivos, RF, HU, roles y trazabilidad.
2. [Arquitectura y decisiones](02-arquitectura.md): tres capas, componentes, flujos, API y estructura realizada.
3. [Modelo de datos](03-modelo-datos.md): diccionario original, límites actuales y esquema v2 para HU02.
4. [Plan de implementación por HU](04-modulos-hu.md): módulos incrementales, dependencias y criterios verificables.
5. [Estándares de desarrollo y seguridad](05-estandares.md): prácticas de código, validación, configuración, UI y operación.
6. [HU01 — Implementación de recolección](10-hu01-recoleccion.md): componentes, endpoints, migración, configuración e inicio local.
7. [Guía de inicio local](11-inicio-local.md): requisitos, instalación de dependencias y pasos para arrancar backend y frontend en Windows.
8. [HU02 — guía del Dataset Histórico](13-hu02-dataset-historico.md): reglas de cohorte, endpoints, interfaz, escenarios demo y tratamiento de filas indeterminadas.
9. [HU03 — Entrenamiento y predicción](14-hu03-entrenamiento-modelo.md): preparación de datos, Random Forest, métricas, artefactos, migración y uso de la interfaz.
10. [HU04 — Consistencia del catálogo](15-hu04-consistencia.md): DecisionTreeClassifier, etiquetas demo, métricas, diagrama del árbol, permisos y persistencia.
11. [HU05 — Reporte semanal de priorización](16-hu05-reporte-priorizacion.md): flujo de datos, prioridades, vista, filtros, exportación, historial, permisos y límites actuales.
12. [Guía de las tablas de la base de datos](17-guia-tablas-base-datos.md): explicación sencilla de las 20 tablas del instalador final y de sus relaciones.
13. [HU08 — Enfoque de indicadores estratégicos](18-enfoque-hu08-indicadores.md): alcance de la simulación, relación de OE1–OE3 con los módulos y lectura de sus límites.
14. [HU08 — Implementación del Dashboard](19-hu08-dashboard.md): tarjetas, metas, datos fuente, evolución, actividad y validación realizada.

## Convenciones

- Los elementos marcados **Definido en el avance** proceden del PDF.
- Los elementos marcados **Decisión de implementación** registran cómo se concretó el diseño en el sistema; los pendientes se identifican explícitamente en su documento correspondiente.
- El prototipo guía la estructura visual, la navegación y el flujo esperado; sus cifras y registros estáticos son de muestra. Los datos funcionales se consultan desde PostgreSQL.
- El backend obtiene la fecha de captura del nombre validado del CSV, calcula semana ISO y audita aparte el momento de importación.
- La salida del catálogo que HU02 deriva comparando snapshots es una etiqueta proxy y no confirma adopción real.
- La base activa es `wuf_predict_db`, con 20 tablas creadas desde el instalador [`../backend/schema_wuf_predict_db.sql`](../backend/schema_wuf_predict_db.sql). El instalador se usa solo al crear una base vacía; no se ejecuta sobre una base con datos. Para las pruebas usa los CSV de [`../data/capturas/escenario_hu02_variable_v4/README.md`](../data/capturas/escenario_hu02_variable_v4/README.md). Los CSV y etiquetas son sintéticos y no representan adopciones ni verificaciones reales.

## Orden de lectura

Leer primero visión y alcance, luego modelo de datos y arquitectura. Implementar las historias en orden de dependencia indicado en `04-modulos-hu.md`; los criterios de HU09 son transversales.
