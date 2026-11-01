# HU08 — Enfoque de indicadores estratégicos

## Contexto del sistema simulado

WUF Predict aplica modelos a CSV de demostración para representar un caso real. Sus resultados sirven para probar la lógica y explicar el apoyo que daría el sistema; no prueban que WUF haya alcanzado efectos en producción. La salida del catálogo de HU02 es un proxy y no confirma una adopción.

## Objetivos vigentes y relación con los módulos

| Objetivo | Indicador que puede mostrar la simulación | Método |
|---|---|---|
| **OE1:** priorizar la difusión de mascotas con baja probabilidad estimada de adopción. | Distribución de probabilidades y prioridades entre las mascotas disponibles. | Random Forest supervisado, HU03. |
| **OE2:** apoyar la revisión del estado publicado. | Perfiles priorizados para revisión y coincidencia del árbol con la regla de referencia. No equivale a exactitud real del catálogo. | Árbol de decisión supervisado, HU04. |
| **OE3:** identificar perfiles desfavorecidos semejantes para orientar análisis/campañas diferenciadas. | Cantidad y composición de los segmentos encontrados en la cohorte HU06; Silhouette como diagnóstico de separación. No se fija una meta de aumento de adopciones. | K-Means no supervisado, HU06. |

La definición inicial de OE3 proponía elevar en 15 % la tasa de adopción usando otro Random Forest. Se reemplaza por la nueva formulación porque el conjunto de prueba no contiene adopciones reales ni resultados de campañas; además, una segunda cifra de probabilidad de adopción se confundía con la estimación OE1. El KPI de la simulación pasa a ser descriptivo: presenta cuántos perfiles hay en cada segmento y sus características. No se interpreta como mejora porcentual de adopciones.

## Datos y flujo de cada objetivo

- **HU01** importa capturas CSV manualmente y conserva una copia del perfil por captura en `snapshot_catalogo`.
- **HU02** compara capturas y produce las clases proxy `permanece` / `salio_catalogo`.
- **OE1 / HU03:** Random Forest aprende con las filas etiquetadas del dataset histórico. Devuelve una probabilidad de salida del catálogo que la interfaz denomina “Probabilidad estimada de adopción” y usa para la prioridad. Es la única probabilidad de adopción mostrada al usuario.
- **OE2 / HU04:** el árbol aprende a aproximar la regla provisional de revisión. Los indicadores reflejan cuánto reproduce esa regla, no si WUF publicó un estado incorrecto real.
- **OE3 / HU06:** la regla HU06 filtra perfiles disponibles con edad de 96 meses o más, tamaño grande o condición especial. Después K-Means los agrupa por similitud. No usa la etiqueta HU02 ni los resultados OE1/OE2.
- **HU05:** muestra OE1 y OE3 en tablas distintas. PDF contiene secciones separadas y Excel hojas separadas; el historial archiva los dos modelos y los perfiles incluidos.

## Detalle de K-Means en OE3

### Cohorte y variables

El modelo se ajusta únicamente con perfiles **disponibles** que cumplen uno o más criterios HU06. Sus variables originales son:

1. Edad en meses.
2. Indicador de edad estimada.
3. Tamaño.
4. Indicador de tamaño estimado.
5. Condición especial.
6. Nivel de energía.

Se excluyen especie, SKU, nombre, orden de publicación, estado, fecha de publicación, etiqueta del dataset y probabilidad OE1. Los identificadores solo se usan para recuperar y mostrar la fila, nunca para formar los grupos.

El pipeline imputa las edades numéricas desconocidas y escala las columnas numéricas; convierte tamaño y energía a columnas categóricas codificadas, imputando sus ausencias si aparecen. La marca de edad estimada se conserva como característica. No se interpreta una edad desconocida como edad baja.

### Entrenamiento y lectura de resultados

El Analista selecciona K entre 2 y 5; la interfaz inicia con K=2 porque en el conjunto actual produce grupos más simples y equilibrados, aunque el Analista puede comparar otras opciones. K-Means minimiza distancias a los centros de los grupos; `random_state` y `n_init` se fijan para hacer repetible el cálculo. Las versiones se guardan aparte de `modelo_predictivo` porque no son clasificadores supervisados.

- **Silhouette** va de −1 a 1: cerca de 1 sugiere grupos separados; cerca de 0, perfiles en fronteras; bajo 0, posibles asignaciones poco coherentes. No es Accuracy y no tiene un umbral de publicación acordado.
- **Inertia** suma las distancias cuadráticas a los centros. Se usa como dato complementario al comparar K; por sí sola baja al aumentar el número de grupos y no define qué K es mejor.
- Las tarjetas resumen cantidad, tamaño/energía más frecuentes, mediana de edad y criterios HU06. Los números “Segmento 1, 2…” son etiquetas nominales: no ordenan grupos por probabilidad ni prioridad y pueden cambiar entre versiones.
- El Analista revisa esos resultados antes de activar el candidato. Tras una nueva captura, debe volver a aplicar la versión activa para asociar perfiles de esa captura con sus grupos.

## Comprobación con los CSV actuales

La validación del algoritmo se realizó con el archivo de la captura final `data/capturas/escenario_hu02_variable_v4/captura_demo_2026-10-12.csv`: 190 perfiles, 86 disponibles y 68 que cumplen la selección HU06. La ejecución de K-Means no usó las etiquetas HU02. Con semilla 42 y 20 reinicios, la prueba de K produjo:

| K | Silhouette | Tamaños observados de los grupos |
|---:|---:|---|
| 2 | 0.2650 | 49, 19 |
| 3 | 0.2454 | 44, 22, 2 |
| 4 | 0.2943 | 14, 39, 13, 2 |
| 5 | 0.2807 | 14, 12, 27, 2, 13 |

Estos resultados muestran que el pipeline sí forma grupos y que la separación es moderada, no perfecta. K=4 obtiene el Silhouette mayor en esta prueba, pero crea un grupo de dos perfiles; K=2 es más sencillo y equilibrado. El Analista puede comparar los resúmenes antes de activar. Ninguno de estos resultados demuestra que un atributo cause la adopción.

Los CSV v4 tienen 180, 165 y 190 filas; la regla HU06 se aplica sobre la última captura al activar o actualizar segmentos. La cantidad de perfiles elegibles puede cambiar entre importaciones.

## Presentación en reportes

- **OE1:** una tabla con atributos del catálogo, probabilidad estimada y prioridad del Random Forest.
- **OE3:** una tabla distinta con SKU/nombre, criterios HU06, segmento K-Means y resumen del grupo. No muestra una probabilidad ni prioridad OE3.
- Los filtros visuales son independientes. Los archivos PDF/Excel exportan las filas completas; Excel separa OE1 y OE3 en hojas distintas.
- Si no hay versión activa o las asignaciones pertenecen a una captura anterior, OE1 sigue disponible si sus datos están completos y OE3 muestra su estado pendiente. No se reutilizan asignaciones viejas como si fueran actuales.
- La exportación guarda referencia a las dos versiones y los snapshots incluidos para permitir descargas históricas reproducibles.

## Reglas de presentación y pendientes de HU08

- Identificar resultados hechos con datos simulados; no etiquetar la distribución de segmentos como tasa de adopción.
- Mantener las métricas técnicas de modelos separadas de indicadores estratégicos. El Silhouette pertenece a OE3; Accuracy de HU03/HU04 no es un KPI estratégico.
- OE1 y OE2 conservan las metas del planteamiento original como objetivos del proyecto, pero la simulación no puede afirmar que las alcanzó en la operación de WUF.
- Antes de construir HU08, acordar el periodo y las fórmulas para mostrar la evolución de OE1/OE2. Para OE3, mostrar cantidad/composición de grupos por captura y versión K-Means; no comparar etiquetas de segmentos entre versiones como si fueran la misma clase.
- Si posteriormente se desea volver a medir incremento real de adopciones, se necesitarían resultados confirmados y un periodo de referencia antes/después de campañas. Ese KPI queda fuera de los datos actuales.
