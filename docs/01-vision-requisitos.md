# Visión, alcance y requisitos

## Propósito

WUF Predict apoya la priorización de difusión de mascotas con menor probabilidad de adopción, la detección de posibles estados obsoletos del catálogo y el seguimiento de indicadores. Es una herramienta de apoyo a decisiones: sus predicciones y alertas requieren revisión humana y no sustituyen la confirmación oficial de una adopción.

## Problema y objetivos

El avance describe un proceso reactivo, sin criterio basado en datos para destacar perfiles; discrepancias entre estado real y publicado; y esperas largas que no se detectan a tiempo. El alcance analítico cubre:

| Objetivo | Indicador/meta del avance | Método indicado |
|---|---|---|
| OE1: priorizar la difusión de mascotas con baja probabilidad de adopción | Aumento de 25% | Clasificación supervisada, Random Forest |
| OE2: mejorar la exactitud del estado del catálogo | 98% | Clasificación supervisada, árbol de decisión |
| OE3: elevar adopciones de perfiles históricamente desfavorecidos | Incremento de 15% | Clasificación supervisada, Random Forest |

El avance informa una prueba de viabilidad con 189 registros: Random Forest con accuracy 84,2%, precision 73,7%, recall 93,3%, F1 82,3% y 76,7% en validación cruzada de cinco particiones; árbol para riesgo con accuracy 89,5%. Son resultados reportados para el dataset de referencia, no garantías de desempeño futuro. Para publicar un modelo, el requisito HU03 fija un umbral mínimo configurable, con valor de demostración de 75% en el prototipo.

## Roles y permisos

| Capacidad | Analista de Datos | Marketing | Área de Ayuda |
|---|:---:|:---:|:---:|
| Dashboard | Sí | Sí | Sí |
| Catálogo y predicción vigente | Sí | Sí | Sí |
| Recolección | Sí | No | No |
| Dataset histórico | Sí | No | No |
| Entrenamiento y métricas | Sí | No | No |
| Alertas | Sí | No | Sí |
| Reporte de priorización | Sí | Sí | No |
| Configuración/perfil | Sí | Sí | Sí |
| Parámetros globales, gestión de permisos | Sí (prototipo) | No | No |

La tabla refleja navegación documentada en el PDF/prototipo; los permisos de operaciones y campos de configuración deben aplicarse en backend, no solo ocultando controles.

## Historias de usuario y criterios

| HU | Historia resumida | Aceptación definida en el avance | Sprint |
|---|---|---|---|
| HU01 | Analista recolecta automáticamente el catálogo | Captura todos los perfiles/atributos/estado; guarda fecha y hora de ejecución | S1 |
| HU02 | Analista construye dataset histórico etiquetado | Atributos + etiqueta adoptada/no adoptada; CSV versionado | S1 |
| HU03 | Analista entrena clasificador de adopción | Registra Accuracy, Precision, Recall, F1; publica solo si supera umbral | S2 |
| HU04 | Área de Ayuda valida consistencia | Cada perfil tiene riesgo; lista casos altos con justificación | S2 |
| HU05 | Marketing genera reporte semanal | Se genera semanalmente, ordenado por prioridad, exportable | S3 |
| HU06 | Marketing identifica perfiles desfavorecidos | Segmenta según edad, tamaño y condición especial | S3 |
| HU07 | Área de Ayuda recibe alertas | Mascota, días sin cambio y riesgo; permite registrar atención | S3 |
| HU08 | Marketing consulta KPI | Tres KPI con meta/evolución y actualización por ejecución | S4 |
| HU09 | Scrum Master documenta y entrega sistema | Manual técnico, manual de usuario y registro de pruebas con resultados | S4 |

Los sprints son de tres semanas, salvo S4 de cuatro semanas; el plan abarca semanas académicas 6 a 18. HU09 es entregable de proyecto, no caso de uso del sistema.

## Requerimientos funcionales

| ID | Requisito resumido | HU | Prioridad |
|---|---|---|---|
| RF01 | Recolectar semanalmente SKU, especie, raza, sexo, edad (exacta/estimada), pelaje, tamaño, energía, condición, descripción hasta 512 caracteres, orden y estado | HU01 | Alta |
| RF02 | Guardar cada captura fechada como snapshot histórico | HU01 | Alta |
| RF03 | Comparar snapshots, etiquetar resultado y producir CSV codificado/versionado | HU02 | Alta |
| RF04 | Entrenar Random Forest con partición configurable | HU03 | Alta |
| RF05 | Calcular y guardar Accuracy, Precision, Recall, F1 y versión | HU03 | Alta |
| RF06 | Predecir probabilidad de adopción y prioridad para mascotas disponibles | HU03, HU05 | Alta |
| RF07 | Evaluar riesgo de estado publicado obsoleto mediante árbol | HU04 | Alta |
| RF08 | Notificar perfiles de alto riesgo al Área de Ayuda | HU07 | Media |
| RF09 | Producir reporte semanal ordenado, exportable a PDF o Excel | HU05 | Media |
| RF10 | Segmentar perfiles desfavorecidos: edad avanzada, tamaño grande, etiquetas de condición | HU06 | Media |
| RF11 | Mostrar KPI OE1-OE3, meta y evolución | HU08 | Media |
| RF12 | Autenticar usuarios y restringir funciones según rol | HU08, HU09 | Baja |

### Adaptación acordada para HU01

La historia y RF01 del avance describen recolección automática semanal. Como el proyecto no dispone de acceso a la plataforma WUF, para el alcance implementable de HU01 se acordó simular la fuente mediante archivos CSV y que el Analista inicie cada importación desde la interfaz. Se conservan los atributos requeridos, la trazabilidad temporal y los snapshots de RF01/RF02; la consulta a WUF y la programación automática quedan fuera de esta entrega. Los CSV de demostración y sus etiquetas son sintéticos y no representan datos observados en WUF.

## Trazabilidad entre requisitos y prototipo

El prototipo es la referencia visual y de flujo para las pantallas login, dashboard, catálogo, recolección, dataset, entrenamiento, alertas, reporte y configuración. Al construir cada módulo se conservarán navegación, jerarquía, componentes, términos y estados visuales; sus cifras y registros de muestra no son datos de negocio. Las rutas (`#dashboard`, `#catalogo`, `#recoleccion`, `#dataset`, `#entrenamiento`, `#alertas`, `#reporte`, `#configuracion`) son referencias de interfaz, no controles de autorización.

Para HU02 el prototipo de Dataset Histórico muestra observaciones por semana y una etiqueta final **“Permanece” / “Salió del catálogo”**. Esta vista se toma como guía funcional para comparar snapshots semanales. El RF03 original expresa esa salida con la interpretación “no adoptado/adoptado”; en la implementación debe quedar claro que la salida del catálogo es una etiqueta derivada/proxy, no confirmación de una adopción real.

## Decisiones y puntos abiertos

1. **Etiqueta HU02 — criterio de trazabilidad:** HU02 compara snapshots sucesivos como pide RF03 y representa las clases del prototipo (“Permanece” / “Salió del catálogo”). La etiqueta se deriva en HU02; `etiqueta_adoptado` no es requisito de entrada y el importador actual descarta esa columna si un CSV antiguo aún la contiene. La salida del catálogo no demuestra por sí sola adopción: los datasets derivados registrarán política y procedencia de etiqueta, y no se presentarán como verdad verificada.
2. **Semántica de estados:** siguiendo las filas del prototipo y RF03, el estado final `disponible` se etiqueta `Permanece`; `no_disponible` se etiqueta `Salió del catálogo` como proxy. Un perfil ausente en una captura completa también puede representar salida; `sin_publicar`, capturas parciales o evidencia insuficiente se marcan indeterminadas. La etiqueta proxy no demuestra adopción.
3. **Fechas y semanas:** la fecha de captura corresponde al periodo representado por el CSV y se lee del patrón validado del nombre (`captura_AAAA-MM-DD.csv` o `captura_demo_AAAA-MM-DD.csv`). La semana mostrada se deriva con calendario ISO; inicio/fin de ejecución conservan el momento de importación. No se usa la hora de importación para simular semanas históricas.
4. **Identidad:** SKU identifica el mismo perfil a través de capturas y debe mantenerse estable en los CSV. Su reutilización para otra mascota invalida la comparación temporal.
5. **OE1/OE3:** el avance no define fórmula, denominador, periodo base ni fuente de adopciones efectivas. Formalizar KPI antes de tratarlos como métricas operativas. Una etiqueta proxy de salida del catálogo no es una tasa verificada de adopción.
6. **OE2:** distinguir accuracy del clasificador de riesgo y exactitud observada del catálogo. Definir fuente de “estado real” y matriz de evaluación.
7. **Probabilidad/prioridad (HU03):** la interfaz usa el término “Probabilidad estimada de adopción”, pero metodológicamente se calcula con la clase `salio_catalogo` derivada en HU02. Es un indicador indirecto, no una adopción confirmada; se informa sin calibración. Menor probabilidad estimada recibe prioridad de difusión más alta. Los cortes de prioridad se configuran por entorno.
8. **Condiciones y edades:** acordar etiquetas canónicas, umbral de “edad avanzada” y manejo de edades estimadas. No inferir umbrales del contenido ilustrativo del prototipo.
9. **Notificación y atención:** el CU07 habla de envío/reintentos pero no especifica canal; HU07 requiere registrar atención. Determinar canal, deduplicación y estados de resolución.
10. **PII:** adoptante, email y teléfono aparecen en el diccionario pero los RF/modelos no los necesitan. No recolectar ni persistirlos hasta justificar finalidad, acceso y retención.
