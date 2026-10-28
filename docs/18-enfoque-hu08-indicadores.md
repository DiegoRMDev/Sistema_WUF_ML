# HU08 — Enfoque de indicadores estratégicos

## Propósito y alcance

WUF Predict es un sistema de Machine Learning simulado aplicado a un negocio real. HU08 presentará cómo los módulos apoyan los objetivos estratégicos con los datos de prueba del proyecto. Los resultados describen el escenario simulado; no prueban que WUF haya alcanzado los mismos efectos en su operación real.

El PDF define estas metas:

| Objetivo | KPI del documento | Meta |
|---|---|---:|
| OE1 — Aumentar la priorización de difusión de mascotas con baja probabilidad de adopción para reducir su permanencia visible. | Nivel de priorización de difusión aplicado a mascotas de baja probabilidad. | Aumento del 25 % |
| OE2 — Mejorar la exactitud del estado del catálogo. | Exactitud del estado del catálogo. | 98 % |
| OE3 — Incrementar las adopciones de perfiles históricamente desfavorecidos por edad, tamaño o condición especial. | Tasa de adopción de perfiles desfavorecidos. | Incremento del 15 % |

Las metas son objetivos del proyecto, no valores que el sistema deba mostrar como ya alcanzados. HU08 debe presentar valor observado en la simulación, meta, periodo, tendencia y estado sin datos cuando corresponda.

## Cómo se relacionan los módulos

- **HU01** importa manualmente los CSV que simulan capturas del catálogo.
- **HU02** compara snapshots y deriva `Permanece` o `Salió del catálogo`. La segunda etiqueta es un proxy de salida, no una adopción confirmada.
- **HU03** entrena el Random Forest con esas etiquetas. Sus probabilidades y prioridades pueden alimentar el análisis simulado de OE1 y OE3.
- **HU04** actualmente asigna prioridades provisionales de revisión mediante una regla y entrena un árbol para aproximarla. Sus métricas comparan el árbol con esa regla; no miden directamente la exactitud del estado publicado requerida por OE2.
- **HU05** presenta/exporta la priorización para apoyar decisiones de difusión; el reporte se genera a demanda, a partir de datos disponibles.
- **HU06** segmenta perfiles por edad avanzada (96 meses o más), tamaño grande o condición especial. Esto identifica la cohorte inicial para el análisis de OE3, pero no calcula por sí solo el KPI.
- **HU08** consolida los KPI y explica su fuente, cálculo, periodo y carácter simulado.

## Fórmulas candidatas para la simulación

El PDF especifica las metas y los nombres de los KPI, pero no fija sus denominadores, línea base ni ventana temporal. Las fórmulas siguientes son una propuesta de trabajo para acordar antes de implementar HU08.

### OE1 — Priorización de difusión

Una medida operativa del nivel de priorización podría ser:

`Cobertura de priorización = mascotas de baja probabilidad que reciben prioridad alta de difusión / total de mascotas elegibles de baja probabilidad × 100`

El aumento se compara con una línea base simulada:

`Aumento relativo = (cobertura del escenario con priorización − cobertura base) / cobertura base × 100`

La meta es 25 % de aumento relativo. Debe acordarse qué banda de HU03 representa “baja probabilidad” y qué significa “recibir difusión” dentro de la simulación. Si no se simulan acciones de difusión, el sistema solo podrá informar cuántas mascotas recomienda priorizar, no cuántas recibieron difusión.

El tiempo promedio visible puede mostrarse como indicador complementario solo si los CSV proporcionan fechas suficientes y una regla consistente para determinar cuándo termina la permanencia. La salida del catálogo no debe etiquetarse como adopción confirmada.

### OE2 — Exactitud del estado del catálogo

En la simulación, cada observación debe tener un estado de referencia conocido, distinto del estado que el sistema estima:

`Exactitud = perfiles cuyo estado estimado coincide con el estado de referencia / total de perfiles evaluados × 100`

La meta es 98 %. La referencia puede ser una etiqueta controlada creada para el escenario de prueba, identificada como simulada. **La implementación actual de HU04 no calcula este KPI:** compara el árbol con prioridades derivadas de una regla de revisión. Antes de presentar Accuracy de HU04 como OE2, se debe definir cómo generar/guardar el estado de referencia y cómo evaluar la predicción de “estado correcto/incorrecto”.

### OE3 — Tasa de adopción de perfiles desfavorecidos

HU06 ya define el conjunto inicial de perfiles desfavorecidos usando edad avanzada (96 meses o más), tamaño grande o condición especial. Las estimaciones se indican y una edad no disponible no satisface el criterio etario.

Para el escenario simulado puede calcularse una tasa proxy:

`Tasa proxy = perfiles desfavorecidos con etiqueta sintética de salida / perfiles desfavorecidos elegibles × 100`

El incremento se compara con una línea base simulada equivalente:

`Incremento relativo = (tasa del escenario con priorización − tasa base) / tasa base × 100`

La meta es 15 %. La etiqueta actual `Salió del catálogo` sirve como proxy para ejercicios del modelo, pero no confirma una adopción. El dashboard debe llamarla tasa proxy/simulada si se usa; no presentarla como tasa real de adopción. Quedan por acordar la cohorte, el periodo, la línea base y cómo interpretar el incremento; HU06 aporta la segmentación, pero no demuestra un aumento de adopciones.

## Reglas de presentación en HU08

- Mostrar **meta**, **valor simulado**, **periodo**, **tendencia**, **fecha de actualización** y una descripción breve de la fuente/fórmula.
- Indicar claramente “Simulación” o “Datos de prueba” cuando el KPI use CSV demo o etiquetas proxy.
- No mostrar la meta como lograda si no se calculó el valor. Sin registros suficientes, mostrar “Sin datos para este periodo”.
- No equiparar Accuracy del modelo con el KPI estratégico: el umbral técnico de publicación de HU03 (75 % por defecto) no es la meta 98 % de OE2.
- No sumar, promediar ni comparar periodos con denominadores distintos sin explicar la fórmula y la cohorte.
- Permitir que los tres roles consulten el dashboard, de acuerdo con el alcance de HU08; las acciones de entrenamiento y administración de datos conservan sus permisos actuales.

## Pendientes antes de implementar los KPI

1. Acordar las fórmulas y la interpretación de “aumento” (relativo o puntos porcentuales) con respecto a la línea base.
2. Definir periodo de comparación y qué ejecuciones/datasets entran en cada cálculo.
3. Definir las acciones simuladas de difusión necesarias para OE1.
4. Alinear HU04 con el objetivo de estado correcto/incorrecto de OE2 o mantener su prioridad de revisión separada y no usar sus métricas como KPI OE2.
5. Acordar la cohorte, el periodo y la línea base para OE3, usando la segmentación definida por HU06.
6. Definir cómo se generan y versionan las etiquetas de referencia simuladas para que los KPI sean reproducibles y auditables.

## Criterio de aceptación para HU08

Cada KPI presenta una cifra derivada de datos persistidos, su meta y periodo, su fórmula/fuente y su condición simulada cuando corresponda. Los casos sin datos se explican sin inventar valores. La documentación y la interfaz distinguen las métricas técnicas de los modelos de los KPI estratégicos.

