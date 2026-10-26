# Implementación incremental por historias de usuario

Las historias son módulos funcionales desplegables por sprint. Las tareas transversales (migraciones, autenticación, logging, errores, documentación) se implementan junto con cada HU; ningún criterio queda como lógica solo de navegador.

## HU01 - Recolección y snapshots (S1, alta)

**Estado de implementación: completada en el alcance acordado.** HU01 usa importación manual de CSV como sustituto de la extracción automática de WUF. El usuario confirmó tres importaciones completadas desde la interfaz; cada archivo mostró 180 perfiles y el historial registró las semanas ISO 40, 41 y 42 (28/09/26, 05/10/26 y 12/10/26), con 108 disponibles, 72 no disponibles y 0 sin publicar por captura. También probó un CSV inválido y confirmó que la validación funcionó. La extracción real desde WUF y la programación semanal se excluyen del alcance implementable acordado.

**Alcance vigente:** importación manual de CSV sintéticos acordada como sustituto de la extracción automática de WUF, que no está disponible para este proyecto. La programación semanal no está implementada. Ver [`01-vision-requisitos.md`](01-vision-requisitos.md) para la adaptación de RF01.

**Objetivo:** conservar capturas trazables del catálogo.

- Definir interfaz `CatalogSource` e implementar `CsvCatalogSource` como fuente de simulación. Cada archivo representa una captura, se consume una vez y se identifica por nombre registrado en `ejecucion_recoleccion`.
- Registrar cada ejecución manual en `ejecucion_recoleccion`: usuario, fecha inicio/fin de procesamiento, semana calendario de la captura, total de perfiles, conteos disponibles/no disponibles/sin publicar, estado, referencia CSV y error resumido. La fecha de captura del contenido y la fecha de importación son conceptos distintos.
- Validar esquema de cada perfil, longitudes, dominios, URLs y campos opcionales; rechazar/poner en cuarentena registros inválidos.
- Actualizar los campos vigentes de `mascota` por SKU estable y crear un `snapshot_catalogo` por mascota/ejecución que copie todos los atributos y estado del CSV. Persistir etiquetas de condición en `snapshot_etiqueta_condicion`.
- Los CSV representan capturas completas y fechadas por el nombre validado del archivo. HU01 conserva atributos/estado observados; HU02 deriva la etiqueta al comparar capturas. `disponible` corresponde a `permanece` y `no_disponible` a `salio_catalogo` según el prototipo/RF03; `sin_publicar` o evidencia incompleta es indeterminada. `etiqueta_adoptado` se acepta solo como campo legado opcional y no es fuente de la etiqueta del dataset.
- Usar la restricción única `(id_ejecucion, id_mascota)` para que repetir el guardado de un perfil dentro de la misma ejecución no duplique snapshots.
- UI de referencia: última captura, selección manual del CSV, conteos y tabla de ejecuciones. “Vigente” se calcula a partir de la última ejecución completada; la pantalla y el endpoint solo son accesibles al Analista.

**Aceptación base:** cada archivo y resultado quedan registrados; cada perfil válido tiene snapshot con atributos, estado y etiquetas de condición; el historial no se reconstruye desde el estado vigente de `mascota`. La fecha/semana ISO provienen de la fecha validada del archivo; inicio/fin registran cuándo se importó. El backend comprueba que mascota, snapshot y ejecución compartan el mismo SKU, semana y fecha de captura.

**Primera entrega técnica:** autenticación y autorización por rol para HU01, consulta paginada de ejecuciones, carga manual de CSV seleccionado por el usuario, vista de última captura y tabla conectada en la copia del prototipo. La fuente CSV y nombre de archivo se registran por ejecución. En una base existente, aplicar las migraciones HU01 previas y `upgrade_hu01_csv.sql`.

**Verificación técnica realizada en esta revisión:** cinco pruebas automatizadas cubren captura válida, fila con varios campos inválidos, SKU repetido dentro del mismo CSV, CSV sin perfiles válidos y nombre ya importado. La revisión de rutas confirma que la carga, el historial y el resumen requieren rol Analista; la fábrica de fuentes impide volver a importar nombres cuya ejecución esté en proceso, completada o parcial. La simulación no satisface la extracción real de WUF ni la periodicidad automática originalmente descritas.

**Seguimiento transversal para HU08:** verificar manualmente que un usuario de otro rol recibe HTTP 403 al consultar o ejecutar las rutas HU01. La autorización está aplicada en el backend; esta prueba con una cuenta distinta se deja para la validación de roles del sistema en HU08. La inspección directa de conteos en PostgreSQL queda como comprobación opcional de persistencia, pues el historial de la interfaz ya confirmó las tres ejecuciones.

## HU02 - Dataset histórico etiquetado/versionado (S1, alta)

**Trazabilidad:** RF03 exige comparar capturas semanales y generar CSV etiquetado; el prototipo muestra una fila por mascota con estados por semana y etiqueta final “Permanece” o “Salió del catálogo”. El criterio original llama a esas clases “no adoptada/adoptada”; por trazabilidad, el sistema puede conservar esa interpretación como proxy, pero debe exponer que la salida del catálogo no confirma adopción.

- Seleccionar un intervalo de capturas y ordenar snapshots por SKU e instante de captura; mostrar las columnas semanales como en el prototipo. La captura debe ser completa para el periodo y usar fecha de captura, no timestamp de importación.
- Derivar etiqueta final desde snapshots consecutivos con regla versionada basada en el prototipo: `disponible` -> `permanece`; `no_disponible` -> `salio_catalogo` (proxy RF03); ausencia en una captura completa -> `salio_catalogo`; `sin_publicar`, captura parcial o evidencia insuficiente -> `indeterminada`.
- La etiqueta de entrenamiento se produce en HU02 y no se exige como verdad de entrada a HU01. `etiqueta_adoptado` queda como dato legado nullable en snapshots, sin uso para el objetivo derivado.
- Exportar un CSV con atributos de la captura de referencia, secuencia/semana de estados, etiqueta final, regla/version, rango, conteos y procedencia. Versionar el dataset y calcular hash para identificar el artefacto reproducible.
- Evitar fuga temporal: las variables predictoras deben preceder al periodo usado para decidir la etiqueta. Conservar los registros `indeterminada` con su motivo en el artefacto auditable HU02; HU03 los excluye al cargar las muestras de entrenamiento.

**Aceptación base:** vista temporal alineada con el prototipo; etiqueta final reproducible y explicable; CSV descargable con versión/metadatos; semana calendario ISO derivada del nombre validado; proxy de salida separado de adopción verificada; evidencia insuficiente informada explícitamente.

**Implementación:** `docs/13-hu02-dataset-historico.md` describe cohorte, selección de periodo/horizonte, endpoints, flujo de pantalla y decisiones de auditoría. Se validó el caso controlado de tres capturas completas de 180 perfiles y el usuario confirmó que la variante 180→165→190 produce el resultado esperado en la interfaz. Los filtros de texto/etiqueta solo modifican las filas visibles; la exportación conserva todas las filas del dataset.

**Decisión de auditoría:** HU02 exporta todos los registros, incluidas filas `indeterminada` con `motivo_indeterminado`. La tabla muestra el motivo junto a la etiqueta; HU03 excluirá esas filas al preparar la muestra de entrenamiento, sin modificar el CSV fuente.

## HU03 - Entrenamiento, evaluación y predicción (S2, alta)

- Entrena Random Forest desde una versión seleccionada de HU02 con pipeline de imputación/codificación, semilla reproducible y partición configurable por grupos SKU. Los atributos son los del snapshot de referencia; estados posteriores, SKU y datos identificadores no son variables predictoras.
- Al preparar las filas, excluye `indeterminada`, conserva el CSV auditable sin modificar y registra cantidad/motivos excluidos. El entrenamiento requiere ambas clases y suficientes ejemplos.
- Evalúa Accuracy, Precision, Recall y F1 sobre prueba, además de matriz de confusión, soporte y conteo por clase. La importancia de variables se presenta como explicación global, no causal.
- El texto visible es **“Probabilidad estimada de adopción”**. Metodológicamente el valor se calcula para la clase `salio_catalogo` de HU02; no es adopción confirmada ni probabilidad calibrada. La regla de prioridad usa bandas configurables y asigna mayor prioridad cuando la estimación es baja.
- Guarda parámetros, semilla, dataset, métricas, versión de librerías, matriz, importancia, artefacto Joblib y su SHA-256. Un modelo debajo del umbral de Accuracy queda no publicable. El Analista publica explícitamente un candidato válido; la activación verifica el hash y genera predicciones para mascotas disponibles ligadas a la ejecución. Tras importar una captura nueva puede actualizar las predicciones del modelo vigente.
- Las métricas de los CSV controlados son demostrativas y no deben presentarse como validadas para adopciones reales ni alimentar KPI reales.
- La interfaz sigue el prototipo: selección de dataset y partición/hiperparámetros, métricas, matriz, importancia, modelo vigente e historial de versiones. El Catálogo consulta predicciones vigentes de la API; no muestra predicciones ilustrativas estáticas.

**Implementación HU03:** ver [`14-hu03-entrenamiento-modelo.md`](14-hu03-entrenamiento-modelo.md). Antes de iniciar el backend sobre una base v2/v3 existente, ejecutar una vez `backend/upgrade_hu03_ml.sql` y reinstalar las dependencias de `backend/pyproject.toml` en `.venv`.

**Estado actual:** backend y frontend integrados y ejecutados localmente por el Analista. Se probaron entrenamientos repetidos, consulta de versiones, publicación explícita, actualización de predicciones y Catálogo; la captura final 180→165→190 coincide con sus CSV y las 86 mascotas disponibles tienen predicción. Se actualizaron los CSV sintéticos de HU02 para incluir nombres plausibles y una asociación moderada de edad, tamaño y condición especial con la etiqueta de salida; el contrato HU01 acepta las tres capturas sin rechazos. La asociación permite explicar el entrenamiento, pero no demuestra causas de adopción real. El detalle y los resultados de referencia están en [`14-hu03-entrenamiento-modelo.md`](14-hu03-entrenamiento-modelo.md) y el README del escenario.

**Aceptación base:** cada modelo publicado puede reproducirse desde dataset/parámetros/artefacto; no se activa con métrica inferior al umbral; la predicción identifica modelo y fecha. El endpoint de entrenamiento actual es síncrono; procesar entrenamientos largos como job queda como trabajo de escalabilidad si el volumen futuro hace que la petición pueda bloquearse. La prueba actual es pequeña y no necesita ese mecanismo.

## HU04 - Riesgo de consistencia (S2, alta)

**Estado de implementación: flujo demo implementado, pendiente de etiquetas reales verificadas.** La sección Entrenamiento permite al Analista entrenar `DecisionTreeClassifier` y elegir profundidad máxima (1–4; valor inicial 3) y porcentaje de prueba (20 %, 25 % o 30 %). Las variables predictoras son días desde publicación y capturas consecutivas disponible; capturas observadas queda en auditoría porque también cuenta estados no disponibles. La regla versionada `prioridad_revision_hu04_v2` establece prioridad alta con al menos tres capturas disponibles consecutivas y 180 días desde publicación; prioridad media si no es alta y cumple al menos dos capturas consecutivas o 60 días; baja en los demás casos. Las secuencias se reinician ante ausencia, estado distinto o fechas repetidas; el intervalo entre capturas debe ser de 1–14 días. La regla asigna directamente las prioridades operativas de **Perfiles para revisión**. El árbol se entrena para aproximarla y sus métricas, matriz, importancia Gini, reglas y diagrama describen ese ajuste; además se registra si cada predicción del árbol coincide con la regla. Así las combinaciones futuras no representadas no cambian la prioridad asignada. Las métricas evalúan la reproducción de etiquetas provisionales, no desactualización real: los CSV no verifican el estado del albergue. La vista identifica el modelo vigente y versiones históricas. Ver [`15-hu04-consistencia.md`](15-hu04-consistencia.md) para límites y evidencia.

Las prioridades siguen siendo etiquetas provisionales derivadas de la regla; las métricas indican si el árbol la reproduce y no validan una detección real. En los CSV demo actuales, la captura final contiene 86 perfiles disponibles: 57 alta, 9 media y 20 baja según la regla v2. Las evaluaciones guardan la prioridad directa de la regla y, por separado, la predicción del árbol y su coincidencia. El esquema limpio [`schema_wuf_predict_v4.sql`](../backend/schema_wuf_predict_v4.sql) incluye las tablas HU04 y solo permite la fuente v2, sin migraciones posteriores. El upgrade [`upgrade_hu04_revision_priority_v2.sql`](../backend/upgrade_hu04_revision_priority_v2.sql) queda para bases antiguas con evaluaciones v1 que deban conservarse. La metodología, configuración e instrucciones están en [`15-hu04-consistencia.md`](15-hu04-consistencia.md).

- Entrenar por grupos de SKU con datos históricos de ejecuciones completas, evitando que una mascota aparezca a ambos lados de la partición.
- Evaluar perfiles disponibles de la última captura completa; guardar árbol/version, parámetros, métricas, artefacto, hash, indicadores y explicación por mascota.
- Diferenciar evaluación HU04 de notificación y atención HU07. La pantalla no afirma que una mascota esté realmente mal publicada; presenta casos para revisar.
- Para pasar de demo a una validación real, el Área de Ayuda debe registrar una verificación independiente del estado de perfiles seleccionados. Luego se reemplazarán las etiquetas derivadas por esas verificaciones.

**Aceptación demo:** perfiles disponibles evaluados reciben nivel y condiciones explicativas; el árbol y resultados quedan versionados; no hay datos o capturas suficientes produce un mensaje de preparación, no un resultado inventado. **Implementación y base de datos:** [`15-hu04-consistencia.md`](15-hu04-consistencia.md), [`../backend/schema_wuf_predict_v4.sql`](../backend/schema_wuf_predict_v4.sql); los scripts de upgrade se usan solo con bases existentes a las que les falten objetos HU04.

## HU05 - Reporte semanal de priorización (S3, media)

La guía detallada del flujo, la vista, la persistencia, los endpoints y las limitaciones está en [`16-hu05-reporte-priorizacion.md`](16-hu05-reporte-priorizacion.md).

- **Estado: completo para el alcance acordado.** La generación programada no se requiere porque HU01 utiliza importación manual de CSV; el reporte conserva la semana ISO de la captura y se genera a demanda.
- **Implementado:** la vista consulta las mascotas disponibles de la última captura completa y las predicciones ligadas al modelo vigente y a esa ejecución. No recalcula probabilidades ni usa predicciones antiguas para completar filas faltantes.
- El reporte ordena por prioridad de HU03 (alta, media, baja) y luego por menor probabilidad, manteniendo el orden de publicación como desempate. Muestra semana ISO, fecha de captura, modelo, resumen de prioridades y tabla con atributos de la mascota, estimación y prioridad.
- El gráfico ofrece una explicación breve de cada nivel de prioridad mediante ayuda accesible con cursor, teclado y toque; el texto refleja la relación entre la estimación y la prioridad de difusión.
- El Analista y Marketing pueden consultar y exportar. Tanto la API como la navegación validan los roles; el filtro por SKU/nombre y prioridad solo afecta la tabla, mientras la exportación incluye todos los registros.
- La exportación genera Excel con `openpyxl` o PDF con ReportLab. Cada exportación inicial registra una versión en `reporte_priorizacion` y copia sus predicciones con `id_reporte`; el historial permite consultar los últimos reportes y regenerar una descarga desde las predicciones y snapshots guardados, sin crear otra versión. No se necesita modificar el esquema v5.
- La generación es a demanda sobre la captura importada, según la adaptación acordada de HU05 descrita en [`01-vision-requisitos.md`](01-vision-requisitos.md). No queda una tarea de programación semanal pendiente.
- Si falta una captura completa, modelo vigente, mascotas disponibles o predicciones para todas las mascotas disponibles, se informa qué debe completarse y no se produce un archivo parcial.
- API: `GET /api/v1/reports/current` entrega el resumen y la tabla; `POST /api/v1/reports/export?formato=pdf|xlsx` genera y registra una nueva exportación; `GET /api/v1/reports/history` lista las últimas 30 versiones; `GET /api/v1/reports/history/{id}/export` vuelve a descargar una versión desde su evidencia guardada. Todos los endpoints están disponibles para Analista y Marketing. Si los datos fuente no están listos, la exportación responde con un error funcional y no crea un reporte.

**Aceptación:** el resumen y la tabla coinciden con la última captura y modelo vigente; PDF y Excel contienen todos los registros con semana, fecha, modelo y prioridades; las descargas quedan auditadas y los roles sin permiso son rechazados.

## HU06 - Perfiles desfavorecidos (S3, media)

- Catálogo de criterios: edad avanzada, tamaño grande y etiquetas de condición especial; configuración/versión de umbrales.
- Segmentar dentro del reporte sin confundir asociación con causalidad ni usar atributo no disponible.
- Mostrar criterios aplicados por perfil y permitir sección vacía informativa.

**Aceptación base:** lista refleja reglas publicadas y permite saber por qué se incluyó cada mascota; casos sin dato se identifican como desconocidos, no como falsos.

## HU07 - Alertas y atención (S3, media)

- Crear alerta de riesgo alto con días sin cambio, historial, explicación, prioridad, fecha y estado pendiente.
- Definir envío (en producto el documento no especifica canal); reintento acotado, deduplicación y registro de fallo.
- Permitir al Área de Ayuda marcar revisada/resuelta y registrar nota/fecha; analista puede consultar.

**Aceptación base:** las alertas se persisten, no se duplican por cada corrida idéntica, son accesibles a roles autorizados y el ciclo de atención queda auditado.

## HU08 - Dashboard (S4, media)

- Consultas agregadas sobre ejecuciones/reportes/adopciones verificadas; filtro temporal y estado “sin datos”.
- Definir fórmulas/denominadores OE1-OE3 con negocio; mostrar meta, valor, tendencia, periodo de cálculo y timestamp.
- Misma API para tres roles; respuesta paginada cuando lista actividad.

**Aceptación base:** cada KPI enlaza definición y fuente; se recalcula tras ejecuciones relevantes; nunca usar números de muestra del HTML como métricas reales.

## HU09 - Entrega documental (S4, baja)

- Mantener manual de arquitectura/técnico, guía de usuario por rol, setup/configuración, migraciones/backup, límites conocidos y modelos.
- Registro de pruebas solicitado en el avance: HU/RF, entorno/dataset versionado, pasos, esperado/observado, resultado y defecto vinculado.
- Evidencia de accesibilidad/responsive, permisos, recuperación de errores y exportaciones.

**Aceptación base:** otra persona puede instalar desde cero con `.env.example`, ejecutar migraciones, iniciar servicios y seguir manuales; resultados de verificación corresponden al commit y entorno indicados.

## Definición de terminado transversal

- Criterios de aceptación satisfechos y vinculados a RF/HU; validaciones server-side; permisos positivos y negativos; migración y rollback revisados.
- Logs/auditoría útiles, errores comprensibles sin filtrar secretos, revisión de datos de prueba.
- UI conserva navegación, responsive, tema, foco visible, etiquetas/semántica y estados vacío/carga/error.
- Contrato API y cambios de esquema documentados; no se publican secretos, datos personales innecesarios ni artefactos sin control.
