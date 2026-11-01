# HU05 — Reporte de priorización y HU06 — Segmentación de perfiles

## Propósito

HU05 ofrece a Marketing una vista y archivos descargables para revisar la última captura completa. El reporte se genera bajo demanda, acorde con la importación manual CSV de HU01. Contiene dos análisis separados:

- **OE1 / HU03:** prioridad de difusión calculada desde la probabilidad del Random Forest.
- **OE3 / HU06:** grupos de perfiles elegibles calculados con K-Means.

OE3 no agrega una segunda probabilidad de adopción. La salida del catálogo usada por OE1 sigue siendo un proxy de adopción, no una confirmación real.

## Datos de OE1

El reporte toma las predicciones ya guardadas para la última captura completada y el modelo Random Forest vigente. No vuelve a entrenar ni recalcula probabilidades. Está listo cuando cada mascota disponible de esa captura tiene una predicción asociada al modelo y a la ejecución correctos.

| Prioridad | Interpretación |
|---|---|
| Alta | Probabilidad estimada más baja; conviene priorizar la difusión. |
| Media | Probabilidad estimada intermedia; mantener difusión regular. |
| Baja | Probabilidad estimada más alta; prioridad menor de difusión. |

Los cortes se configuran con `MODEL_PRIORITY_HIGH_MAX` y `MODEL_PRIORITY_MEDIUM_MAX` en el entorno. No son umbrales validados por WUF. El listado se ordena alta, media y baja, luego por probabilidad ascendente, orden de publicación descendente y SKU.

## Datos de OE3 y K-Means

HU06 selecciona de la captura vigente perfiles disponibles con al menos un criterio: edad de 96 meses o más, tamaño grande o condición especial. Edades estimadas pueden calificar y se marcan; una edad no indicada no cumple el criterio de edad. Los criterios se pueden superponer.

El modelo K-Means activo asigna a cada perfil elegible un número de segmento. Usa seis variables de perfil: edad en meses, edad estimada, tamaño, tamaño estimado, condición especial y nivel de energía. **No usa especie, SKU, nombre, orden de publicación, estado, etiquetas HU02 ni probabilidades/prioridades OE1.** El primer filtrado por criterios es una regla de negocio para definir la cohorte; la agrupación dentro de esa cohorte sí la realiza K-Means.

La tabla de perfiles agrupados presenta SKU/nombre, motivos de inclusión (edad avanzada, tamaño grande o condición especial), segmento y resumen del grupo (tamaño/energía frecuentes y mediana de edad). Los números de segmento son nombres internos, no niveles ordenados, clases de adopción ni prioridades. Silhouette aparece en el área de entrenamiento como diagnóstico; no se presenta como Accuracy.

El Analista entrena versiones con K de 2 a 5, revisa silhouette y tamaños/resúmenes de grupos, y activa una versión. El artefacto activo se aplica a la captura disponible; tras importar una captura nueva, el Analista usa **Actualizar captura** para guardar asignaciones del nuevo snapshot. Si las asignaciones OE3 no corresponden a la última captura, el reporte lo indica como pendiente y no reutiliza resultados antiguos.

## Corrección del enfoque de OE3

OE3 ahora agrupa perfiles semejantes con K-Means; no calcula una segunda probabilidad de adopción. La única probabilidad de adopción visible para Marketing es la estimación de HU03 (OE1). La tabla de segmentación muestra el segmento y sus características descriptivas.

Un perfil disponible entra a HU06 si cumple **al menos uno** de estos criterios: edad de 96 meses o más (ocho años), tamaño grande o condición especial. Una edad desconocida no cumple por sí sola el criterio de edad. Las edades y tamaños estimados sí pueden cumplir y se señalan como estimados. Los motivos pueden superponerse.

K-Means agrupa la cohorte usando edad, marca de edad estimada, tamaño, marca de tamaño estimado, condición especial y nivel de energía. Los valores numéricos faltantes se imputan con la mediana y mantienen una marca de ausencia; los numéricos se escalan y las categorías se codifican para que el algoritmo las procese. La especie y los identificadores quedan fuera. El analista puede elegir K entre 2 y 5; la semilla y los reinicios se mantienen fijos para que las comparaciones sean reproducibles.

**Silhouette** es un diagnóstico de cohesión y separación de los grupos, con valores entre -1 y 1: más cerca de 1 suele indicar grupos mejor separados, cerca de 0 indica solapamiento y un valor negativo puede señalar asignaciones poco adecuadas. No es Accuracy, no mide adopción y no tiene un umbral universal que garantice una segmentación correcta. Se interpreta junto con los tamaños y las descripciones de los grupos.

El gráfico de dispersión usa PCA para proyectar los perfiles en dos ejes y facilitar su lectura. Los porcentajes de esos ejes indican cuánta variación de los datos se ve en el plano; el porcentaje restante queda fuera de la imagen, pero K-Means sí usa todas las variables transformadas para formar los grupos.

## Vista

La interfaz conserva el estilo del prototipo y muestra:

- Semana, fecha de captura y cantidad disponible.
- Gráfico de barras de mascotas por prioridad.
- Tabla **Mascotas ordenadas por prioridad**, con una sola probabilidad de adopción y prioridad.
- Resumen y tabla independientes de perfiles desfavorecidos agrupados, sin una segunda probabilidad ni prioridad de adopción.
- Búsqueda por SKU/nombre y filtro por prioridad en OE1; búsqueda y filtro por segmento en OE3. Los filtros afectan solo las filas visibles.
- Exportar PDF/Excel e historial con versiones de los dos modelos y conteos separados.

Si OE1 tiene datos completos y OE3 no tiene modelo activo, la tabla OE1 sigue disponible. OE3 explica que falta entrenar/activar o actualizar K-Means. Las exportaciones incluyen todos los datos disponibles: el Excel tiene hojas separadas para cada objetivo y el PDF secciones separadas.

## Flujo de exportación e historial

1. `GET /api/v1/reports/current` obtiene la captura final, predicciones OE1, versión activa de K-Means y asignaciones ligadas a snapshots.
2. La API verifica que todas las mascotas disponibles tengan predicción OE1 completa y válida.
3. Los criterios HU06 y las asignaciones OE3 se entregan como colección separada.
4. PDF se genera con ReportLab y Excel con openpyxl. La exportación no depende de filtros del navegador.
5. `reporte_priorizacion` guarda la captura y las versiones de modelo. Predicciones OE1 se copian con `id_reporte`; `reporte_segmento_detalle` enlaza las asignaciones OE3 exactas para reproducir el archivo histórico.

Las descargas del historial reconstruyen los archivos desde filas y snapshots preservados; no reejecutan los modelos ni crean una nueva exportación.

## Persistencia

K-Means no se guarda en `modelo_predictivo`: esa tabla describe el Random Forest supervisado y sus métricas/clases. OE3 usa:

- `modelo_segmentacion`: versión K-Means, ejecución de referencia, K, silhouette, inertia, variables/parámetros, resúmenes de grupos y hash del artefacto.
- `asignacion_segmento`: segmento asignado por modelo y snapshot, más los criterios HU06 observados.
- `reporte_segmento_detalle`: conserva qué asignaciones exactas se incluyeron en una exportación.
- `reporte_priorizacion`: referencia ejecución y modelo OE3 junto con el reporte existente de OE1.

El esquema limpio v6 contiene 22 tablas. Para usar el código actualizado, crear una base limpia nueva `wuf_predict_v8`, ejecutar [`../backend/schema_wuf_predict_v6.sql`](../backend/schema_wuf_predict_v6.sql) una sola vez y cambiar `DATABASE_URL` en `backend/.env`. La base anterior `wuf_predict_v7` y sus datos permanecen intactos; no se debe ejecutar el instalador v6 sobre ella. Reimporta los CSV de demostración y recrea el usuario Analista en la base nueva.

## Roles y endpoints

| Endpoint | Función | Permisos |
|---|---|---|
| `GET /api/v1/reports/current` | Devuelve la vista de OE1 y OE3, con estado por objetivo. | Analista, Marketing |
| `POST /api/v1/reports/export?formato=pdf\|xlsx` | Exporta y registra el reporte completo. | Analista, Marketing |
| `GET /api/v1/reports/history` | Lista hasta 30 exportaciones y sus modelos/conteos. | Analista, Marketing |
| `GET /api/v1/reports/history/{id}/export` | Vuelve a generar una descarga histórica. | Analista, Marketing |
| `GET /api/v1/segmentation/options` | Muestra la captura y cantidad de perfiles disponibles para K-Means. | Analista |
| `GET /api/v1/segmentation/models` | Consulta versiones, resumen y estado de K-Means. | Analista |
| `POST /api/v1/segmentation/models/train` | Entrena un candidato con K seleccionado. | Analista |
| `POST /api/v1/segmentation/models/{id}/activate` | Activa un candidato y guarda asignaciones de la captura vigente. | Analista |
| `POST /api/v1/segmentation/models/current/refresh` | Reaplica el modelo vigente a la última captura. | Analista |

La autorización se valida en el backend; ocultar opciones en el frontend no sustituye ese control.

## Límites

- El dataset demo es pequeño y sintético; la agrupación describe esos perfiles, no toda la población de WUF.
- Silhouette depende de K y de la distribución de cada captura. No mide adopción ni calidad de campañas.
- Los grupos pueden cambiar de un entrenamiento a otro y sus números no son etiquetas estables.
- La propuesta inicial de una meta de +15 % de adopciones para OE3 se sustituyó por la cantidad y composición de los segmentos; medir un aumento de adopciones requeriría resultados reales de campañas y adopciones confirmadas.
- La segmentación es una herramienta de exploración. Marketing puede revisar los grupos junto a OE1, pero la prioridad de difusión sigue siendo la del Random Forest.
