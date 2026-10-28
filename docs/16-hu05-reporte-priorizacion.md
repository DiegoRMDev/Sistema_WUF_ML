# HU05 — Reporte semanal de priorización y HU06 — Perfiles desfavorecidos

## Propósito y alcance

HU05 presenta al equipo una lista ordenada de mascotas disponibles para orientar la difusión. HU06 añade a esa misma vista la segmentación de perfiles con atributos desfavorecidos, siguiendo la tabla del prototipo. Por acuerdo, la generación programada semanal no forma parte del alcance: como HU01 simula la recolección con importación manual de CSV, el reporte se consulta y exporta a demanda para la semana ISO de la última captura completa.

El reporte utiliza las predicciones que HU03 ya guardó para la última captura completa y el modelo vigente. No vuelve a entrenar el Random Forest ni recalcula probabilidades. Solo está listo cuando hay una captura, un modelo vigente y una predicción de ese modelo para cada mascota disponible de la captura.

## Significado y orden de las prioridades

La probabilidad mostrada como **Probabilidad estimada de adopción** se calcula metodológicamente a partir de la clase `salio_catalogo` de HU02. Es una señal indirecta, no una confirmación de adopción real.

El backend compara esa probabilidad con las bandas configurables `MODEL_PRIORITY_HIGH_MAX` y `MODEL_PRIORITY_MEDIUM_MAX`:

| Prioridad | Interpretación en la vista |
| --- | --- |
| Alta | Probabilidad estimada más baja; conviene dar mayor prioridad a la difusión. |
| Media | Probabilidad estimada intermedia; mantener una difusión regular. |
| Baja | Probabilidad estimada más alta; prioridad menor de difusión. |

Los cortes de ejemplo son 0.35 y 0.65, pero se pueden configurar en `backend/.env`. No son umbrales operativos validados por WUF. El orden es alta, media y baja; dentro de cada nivel se ordena por probabilidad ascendente y luego por orden de publicación descendente, con SKU como desempate. Las ayudas breves del gráfico aclaran estos niveles mediante cursor, teclado y toque. El gráfico usa una separación visual entre su título y las columnas.

## Vista y acciones disponibles

La pantalla del reporte contiene:

- Un resumen con semana ISO, fecha de captura, cantidad de mascotas disponibles y versión del modelo.
- Un gráfico de barras con la cantidad de perfiles en cada prioridad y una ayuda accesible por nivel.
- Un buscador por SKU o nombre y filtros por prioridad y atributo desfavorecido. Solo filtran las filas visibles en la tabla; no alteran los datos que se descargan.
- Un resumen del segmento desfavorecido con conteos por criterio y una tabla con los criterios que cumple cada perfil.
- Una tabla de mascotas disponibles con scroll vertical y horizontal. Incluye atributos relevantes, probabilidad estimada y prioridad.
- Acciones para exportar el reporte completo como PDF o Excel.
- Un historial de las últimas 30 exportaciones, con fecha, semana, versión de modelo, formato, cantidad de registros y usuario que lo generó. Desde cada fila se puede volver a descargar el documento.

El Analista y Marketing pueden consultar y exportar. El backend aplica la autorización en cada endpoint, además de ocultar las opciones que no corresponden en la navegación. Los demás roles reciben una respuesta de acceso denegado si llaman directamente a la API.

## Flujo de datos

1. La vista solicita el reporte vigente a `GET /api/v1/reports/current`.
2. El servicio elige la última ejecución completada y el modelo predictivo marcado como vigente.
3. Se cargan las predicciones asociadas tanto a ese modelo como a esa ejecución, junto con los datos del snapshot de catálogo.
4. Se comprueba que todas las mascotas disponibles tengan exactamente una predicción con prioridad válida. Si faltan datos, se muestra un mensaje y no se prepara una exportación parcial.
5. El servicio deriva los criterios HU06 desde los atributos del snapshot. El cliente muestra el resumen, las barras y la tabla, y permite filtrar por prioridad y atributo.
6. Al exportar, el backend genera el formato solicitado y registra una versión del reporte.

La respuesta del reporte incluye todas las mascotas disponibles, sus criterios HU06 y los conteos por criterio. Los criterios pueden superponerse; el total del segmento cuenta mascotas únicas. Los filtros de la interfaz no se envían al exportador: PDF y Excel siempre contienen todos los registros ordenados e incluyen una columna con las razones de segmentación. Valores estimados se marcan y una edad no indicada no se trata como un valor negativo.

## HU06 — Implementación y alcance

**Estado: completo para el alcance acordado.** El segmento incluye perfiles que cumplen uno o más criterios: edad de al menos 96 meses, tamaño grande o condición especial. Cada mascota aparece una vez y muestra todas las razones. Edades y tamaños estimados se marcan; la edad desconocida no satisface el criterio de edad, aunque no impide calificar por otro atributo.

La vista muestra el total único, conteos por criterio y filtros; las exportaciones PDF/Excel incluyen todos los perfiles y sus razones, sin depender de los filtros visuales. Para la captura final del conjunto v4, la referencia es 68 de 86 perfiles disponibles (53 por edad, 21 por tamaño y 19 por condición; los grupos se superponen).

La segmentación usa los atributos conservados en `snapshot_catalogo`; no requirió cambios de base de datos y no modifica probabilidades ni prioridades del Random Forest. Identifica atributos asociados, no causalidad ni adopciones confirmadas. El cálculo del KPI OE3 corresponde a HU08.

## Exportación y auditoría

`openpyxl` genera el archivo Excel y ReportLab genera un PDF apaisado. Ambos incluyen todos los registros y una columna con los criterios HU06; los filtros visuales no afectan el archivo. Cada exportación inicial agrega un registro a `reporte_priorizacion` con usuario, semana, fecha de generación y formato. También copia las predicciones con `id_reporte`, conservando modelo, ejecución, probabilidad y prioridad. Las características de cada mascota se recuperan del snapshot de esa ejecución, no de los valores actuales de la tabla `mascota`.

La sección de historial llama a `GET /api/v1/reports/history`. Para volver a descargar un registro utiliza `GET /api/v1/reports/history/{id}/export`; este endpoint reconstruye el archivo desde el snapshot y las predicciones persistidas. Repetir una descarga no crea otra versión. El historial presenta hasta 30 exportaciones recientes.

La base actual `wuf_predict_v6` ya conserva en `snapshot_catalogo` la edad, sus marcas de estimación, tamaño y condición especial. HU06 calcula el segmento a partir de esos datos y no requiere modificar el esquema ni crear otra base. Al volver a descargar un reporte histórico, las razones se reconstruyen desde el snapshot original usando la regla actual.

## Endpoints

| Método y ruta | Función | Roles |
| --- | --- | --- |
| `GET /api/v1/reports/current` | Obtiene resumen y filas del reporte vigente. | Analista, Marketing |
| `POST /api/v1/reports/export?formato=pdf` o `?formato=xlsx` | Genera y registra una nueva exportación. | Analista, Marketing |
| `GET /api/v1/reports/history` | Lista las 30 exportaciones más recientes. | Analista, Marketing |
| `GET /api/v1/reports/history/{id}/export` | Regenera una descarga histórica desde los datos guardados. | Analista, Marketing |

## Dependencias y ejecución local

Las dependencias `openpyxl` y `reportlab` están declaradas en `backend/pyproject.toml`. Instálalas junto con las demás dependencias del proyecto desde el entorno virtual:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Reinicia el backend después de instalar dependencias o incorporar cambios en la API. Recarga el frontend para cargar sus archivos actualizados.

## Criterios cubiertos y límites

- HU05 se considera completa con el flujo acordado: reporte correspondiente a la semana de captura, disponible a demanda, ordenado y exportable. La ausencia de un programador semanal no es una tarea pendiente.
- HU06 cuenta con la segmentación inicial en la vista del reporte y en los dos formatos de exportación, sin alterar la prioridad calculada por HU03.
- El resumen y las filas usan la misma captura completa, modelo vigente y ejecución de las predicciones.
- Una predicción faltante no se sustituye por otra versión ni por una estimación nueva calculada al vuelo.
- El filtro de pantalla no cambia el conjunto exportado.
- Cada exportación es auditable y puede recuperarse desde el historial.
- Las prioridades dependen de bandas configurables y de etiquetas proxy de HU02; no constituyen una adopción confirmada ni una validación de efectividad de campañas.
- La carga de CSV en HU01 y la generación/exportación del reporte son acciones manuales; esta es la adaptación acordada y no una limitación pendiente de HU05.
