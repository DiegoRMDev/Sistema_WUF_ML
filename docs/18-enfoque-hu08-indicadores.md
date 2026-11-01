# HU08 — Enfoque de indicadores estratégicos

## Contexto del sistema simulado

WUF Predict aplica modelos a CSV de demostración para representar un caso real. Los resultados sirven para probar la lógica y explicar el apoyo que daría el sistema; no demuestran efectos en producción. La salida del catálogo usada por HU02 es un proxy y no confirma una adopción real.

## Objetivos y relación con los módulos

| Objetivo | Indicador disponible en la simulación | Método |
|---|---|---|
| **OE1:** priorizar la difusión de mascotas con baja probabilidad estimada de adopción. | Distribución de probabilidades y prioridades entre las mascotas disponibles. | Random Forest supervisado, HU03. |
| **OE2:** apoyar la revisión del estado publicado. | Perfiles priorizados para revisión y coincidencia del árbol con una regla de referencia. No equivale a exactitud real del catálogo. | Árbol de decisión supervisado, HU04. |
| **OE3:** descubrir segmentos de mascotas disponibles y ubicar perfiles con atributos desfavorecidos dentro de ellos. | Cantidad y composición de grupos, más el número y porcentaje de perfiles con criterios desfavorecidos en cada grupo. | K-Means no supervisado, HU06. |

OE3 no estima adopción ni mide un aumento de adopciones. K-Means encuentra grupos por similitud; luego reglas de negocio identifican edad avanzada, tamaño grande y condición especial. Esto evita presentar una segunda probabilidad de adopción que se confunda con OE1.

## Flujo de datos

- **HU01** importa CSV manualmente y conserva una copia del perfil por captura en `snapshot_catalogo`.
- **HU02** compara capturas y produce las etiquetas proxy `permanece` / `salio_catalogo`.
- **OE1 / HU03:** Random Forest aprende con las filas etiquetadas del dataset histórico. Devuelve una probabilidad de salida del catálogo que la interfaz denomina “Probabilidad estimada de adopción” y usa para asignar prioridad.
- **OE2 / HU04:** el árbol aprende a aproximar la regla provisional de revisión. Sus métricas indican cuánto reproduce esa regla, no si WUF publicó un estado incorrecto real.
- **OE3 / HU06:** K-Means agrupa todas las mascotas disponibles usando edad, edad estimada, tamaño, tamaño estimado, condición especial y energía. No usa especie, SKU, nombre, orden, estado, etiqueta HU02 ni probabilidades/prioridades OE1. Después se anotan los criterios de perfil desfavorecido.
- **HU05:** presenta OE1 y OE3 en tablas independientes. Los PDF/Excel conservan las secciones y los datos por separado.

## Criterios descriptivos de perfiles desfavorecidos

Los criterios no definen qué mascotas ingresan al algoritmo ni el segmento que reciben. Se aplican como anotaciones después de entrenar y asignar K-Means:

- Edad avanzada: 96 meses o más (ocho años). Si es estimada, se indica como tal; edad desconocida no satisface el criterio.
- Tamaño grande. Un tamaño estimado puede calificar y se marca.
- Condición especial.

Los criterios pueden superponerse. Cada perfil disponible puede estar en cualquier segmento, tenga o no criterios. Los resúmenes muestran, dentro de cada segmento, cuántos perfiles y qué porcentaje cumplen al menos uno; los conteos individuales por criterio pueden sumar más que el total por superposición.

## Preparación y lectura de K-Means

El pipeline imputa edades numéricas faltantes con la mediana y conserva una marca de ausencia; escala variables numéricas y codifica las categorías de tamaño y energía. Las marcas de edad/tamaño estimado son características. La semilla y `n_init` se fijan para reproducibilidad. El Analista elige K de 2 a 5; cada versión guarda su captura de referencia y se aplica a la captura vigente al activarse o actualizarse.

- **Silhouette** va de −1 a 1. Cerca de 1 sugiere grupos separados; cerca de 0 indica solapamiento; valores negativos pueden señalar asignaciones poco coherentes. No es Accuracy, no mide adopción ni tiene un umbral universal.
- **Inertia** suma las distancias cuadráticas a los centros. Ayuda a comparar K, pero normalmente baja al agregar grupos y no basta por sí sola para elegir K.
- Los nombres “Segmento 1”, “Segmento 2”… son etiquetas nominales, no rangos de calidad ni adopción; pueden cambiar entre entrenamientos.
- El gráfico usa PCA para mostrar los puntos en dos ejes. Sus porcentajes describen la variación visible en esa proyección; K-Means calcula grupos con todas las características procesadas, no solo con los dos ejes.

## Comprobación con los CSV demo

La captura final `data/capturas/escenario_hu02_variable_v4/captura_demo_2026-10-12.csv` tiene 190 perfiles, 86 disponibles y 68 que cumplen uno o más criterios desfavorecidos. Para el enfoque actual se agrupan los 86 disponibles; las 68 coincidencias solo se cuentan y describen después.

Con semilla 42 y 20 inicializaciones, se reprodujo el orden por SKU que aplica el backend al leer PostgreSQL. El orden de filas importa para la inicialización de K-Means; con el mismo seed, otro orden puede converger a otra solución local.

| K | Silhouette | Tamaños de los grupos | Perfiles con criterios por grupo |
|---:|---:|---|---|
| 2 | 0.510 | 83, 3 | 66/83 (79.5 %), 2/3 (66.7 %) |
| 3 | 0.243 | 27, 56, 3 | 22/27 (81.5 %), 44/56 (78.6 %), 2/3 (66.7 %) |
| 4 | 0.279 | 24, 44, 15, 3 | 20/24 (83.3 %), 33/44 (75.0 %), 13/15 (86.7 %), 2/3 (66.7 %) |
| 5 | 0.283 | 16, 15, 14, 38, 3 | 12/16 (75.0 %), 13/15 (86.7 %), 14/14 (100 %), 27/38 (71.1 %), 2/3 (66.7 %) |

Las proporciones describen estas capturas sintéticas y no validan una estrategia de adopción. En K=2, el Silhouette alto refleja principalmente que las tres mascotas sin edad indicada forman un grupo pequeño y separado; el otro grupo contiene 83 de los 86 perfiles, por lo que aporta poca segmentación operativa. K=4 ofrece un compromiso más útil: tres grupos de 15 a 44 mascotas con diferencias descriptivas y un grupo de tres sin edad indicada. K=5 tiene el Silhouette más alto entre K=3–5 y forma un grupo de 14 perfiles con condición especial, pero agrega complejidad y mantiene el grupo pequeño de datos incompletos. Para presentar el resultado, elegir K=4 como equilibrio entre detalle, lectura sencilla y tamaño de grupos; explicar que el grupo de tres representa falta de edad, no una categoría de adopción. No se declara un K universalmente óptimo. Los tres CSV v4 tienen 108, 87 y 86 disponibles respectivamente, suficientes para comparar K de 2 a 5; aun así pueden aparecer grupos pequeños. La cantidad de disponibles y la cantidad con criterios cambian entre capturas.

En la captura demo actual, K=4 se interpreta así: **Segmento 1 (24)** reúne principalmente mascotas grandes y de energía baja; mediana de edad 121 meses y 20 cumplen uno o más criterios desfavorecidos. **Segmento 2 (44)** es el grupo más numeroso, principalmente mediano y de energía baja; mediana de 123 meses y 33 cumplen criterios. **Segmento 3 (15)** agrupa principalmente perfiles medianos de energía alta; mediana de 143 meses y 13 cumplen criterios. **Segmento 4 (3)** concentra los perfiles sin edad registrada; solo 2 cumplen algún otro criterio. Las edades estimadas son más frecuentes en el primero (24) y aparecen en tres perfiles del tercero. Son descripciones de los grupos, no etiquetas de riesgo ni predicciones de adopción; los criterios pueden superponerse y el segmento 4 es demasiado pequeño para generalizar.

## Presentación y exportación

- **OE1:** tabla con atributos, probabilidad estimada y prioridad Random Forest.
- **OE3:** tabla separada con SKU/nombre, criterios descriptivos, segmento y resumen de grupo. No muestra probabilidad de adopción.
- Filtros de interfaz no cambian el conjunto exportado. Excel separa OE1/OE3 en hojas y PDF usa secciones separadas.
- Si no existe K-Means activo compatible con todo el catálogo, OE1 sigue disponible y OE3 solicita entrenar/activar una versión actual. Los modelos históricos del enfoque filtrado se conservan como consulta, pero no se reutilizan para asignar el catálogo completo.
- Las exportaciones guardan las predicciones, asignaciones, snapshots y versiones usados, de forma que puedan volver a descargarse sin ejecutar de nuevo los algoritmos.

## Persistencia y roles

La versión K-Means usa `modelo_segmentacion`, `asignacion_segmento` y `reporte_segmento_detalle`; `modelo_predictivo` sigue representando el Random Forest de OE1. El campo JSONB `parametros.cohort_scope` identifica si el modelo se entrenó con el catálogo completo. Las versiones anteriores quedan disponibles en historial y no requieren migración para esta modificación.

El Analista puede entrenar, activar y actualizar K-Means; Analista y Marketing consultan/exportan el reporte. La autorización se comprueba también en el backend.

## Dashboard HU08 implementado

La vista resume datos de las tablas existentes; no modifica capturas, predicciones ni modelos y no necesita tablas nuevas. `GET /api/v1/dashboard/summary` requiere una sesión iniciada y acepta los tres roles. El servicio reúne la última captura completada, resultados vinculados a cada captura, actividad reciente y hasta seis capturas históricas. La cantidad de filas se configura con `DASHBOARD_HISTORY_CAPTURE_LIMIT` y `DASHBOARD_ACTIVITY_LIMIT`.

La pantalla presenta:

- **OE1:** número de mascotas disponibles con prioridad alta de la predicción Random Forest y total disponible. La meta se muestra como aumento de priorización de **+25 %**; el conteo no demuestra que el aumento se haya alcanzado.
- **OE2:** número de alertas abiertas de riesgo alto, rotulado como perfiles para revisar. La meta de exactitud **98 %** aparece separada; no se presenta como un porcentaje medido porque falta una fuente independiente de estado real.
- **OE3:** perfiles disponibles con uno o más criterios desfavorecidos. Si existen asignaciones K-Means para esa captura, también muestra cantidad de segmentos y la proporción de perfiles elegibles que quedaron asignados. La meta operativa adoptada es cobertura de **100 % por captura**; no significa aumento real de adopciones.
- **Última captura:** total de perfiles, estados y distribución de prioridades cuando hay predicciones.
- **Evolución por captura:** valores guardados para cada captura; una celda queda como “—” si todavía no existe un resultado de ese módulo para esa fecha.
- **Actividad reciente:** importaciones, datasets, entrenamientos, exportaciones y atención de alertas, con fecha y detalle breve.

Las metas se leen de la configuración `DASHBOARD_OE1_TARGET_INCREASE_PERCENT`, `DASHBOARD_OE2_TARGET_ACCURACY_PERCENT` y `DASHBOARD_OE3_TARGET_COVERAGE_PERCENT`; sus valores de ejemplo son 25, 98 y 100. En la interfaz no se usan los números ilustrativos del prototipo como resultados.

## Límites

- Los CSV son sintéticos; OE3 describe estos datos, no a toda la población de WUF.
- La proporción desfavorecida por segmento no es una tasa ni incremento de adopción.
- La Silhouette depende de la captura, K y distribución; no mide el éxito de campañas.
- Las comparaciones del histórico son por captura. Los identificadores de segmentos son nominales y no deben interpretarse como categorías equivalentes entre entrenamientos.
- Medir un cambio real en adopciones requiere resultados confirmados y observaciones de campañas, fuera de los datos actuales.
