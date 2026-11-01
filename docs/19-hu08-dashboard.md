# HU08 — Dashboard de indicadores

## Propósito

Reunir en una vista los resultados recientes de los módulos para que Analista, Marketing y Área de Ayuda consulten el catálogo, las metas y la evolución de las capturas. Los valores se leen de PostgreSQL; no son cifras fijas del prototipo.

## Qué muestra

- **Priorización de difusión:** perfiles disponibles con prioridad alta del Random Forest y total de perfiles disponibles. La meta de aumento es +25 %.
- **Perfiles por revisar:** alertas abiertas de riesgo alto. La meta de exactitud del catálogo (98 %) aparece como referencia separada; el conteo de alertas no mide esa exactitud.
- **Perfiles desfavorecidos:** perfiles disponibles que cumplen uno o más criterios. Cuando hay asignaciones K-Means para la captura, también se muestra su cobertura y la cantidad de segmentos. La meta operativa de cobertura es 100 % por captura.
- **Última captura:** perfiles totales y sus estados; cuando existen predicciones, también incluye el reparto por prioridad.
- **Evolución por captura:** resultados disponibles para las últimas capturas completas. Se muestra “—” cuando un módulo aún no generó resultados para esa captura.
- **Actividad reciente:** importaciones CSV, datasets, entrenamientos, aplicación de Random Forest al catálogo y K-Means al reporte de priorización, exportaciones y atención de alertas.

Las detecciones de riesgo alto se agrupan en una sola fila por evaluación del árbol, con la semana y la cantidad de perfiles señalados. La lista tiene desplazamiento propio para mantener compacta la pantalla.

## Datos y funcionamiento

La ruta autenticada `GET /api/v1/dashboard/summary` consulta `ejecucion_recoleccion`, `snapshot_catalogo`, `prediccion`, los resultados de consistencia y segmentación, alertas, datasets y reportes. No agrega tablas ni modifica los resultados. La vista vuelve a consultar al abrirse o al regresar a ella; las cantidades de historial y actividad se limitan mediante `DASHBOARD_HISTORY_CAPTURE_LIMIT` y `DASHBOARD_ACTIVITY_LIMIT`.

La actividad de captura muestra la hora de importación, convertida de UTC a la hora de Lima. “Catálogo actualizado con Random Forest” registra las predicciones aplicadas al catálogo; “Reporte de priorización actualizado con K-Means” registra las asignaciones de segmentos que se usarán en ese reporte.

Las metas se pueden configurar en `backend/.env`:

| Variable | Valor de ejemplo |
|---|---:|
| `DASHBOARD_OE1_TARGET_INCREASE_PERCENT` | 25 |
| `DASHBOARD_OE2_TARGET_ACCURACY_PERCENT` | 98 |
| `DASHBOARD_OE3_TARGET_COVERAGE_PERCENT` | 100 |

Los valores predeterminados aplican si estas variables no se agregan al `.env` existente.

## Alcance y límites

El sistema usa CSV de demostración y etiquetas proxy. El conteo de prioridad alta no demuestra que se haya alcanzado un aumento de 25 %. La cantidad de alertas abiertas es una señal operativa y no una medición de exactitud real; para medir el 98 % se necesitarían estados reales verificados. La cobertura K-Means indica cuántos perfiles elegibles fueron agrupados en una captura, no un aumento de adopciones.

## Validación realizada

La consulta de solo lectura a la base configurada comprobó que los valores y las filas históricas cambian según las capturas y resultados persistidos. La API respondió `401` sin sesión y `200` con la cuenta Analista existente. En esa base no hay cuentas Marketing ni Área de Ayuda; el endpoint las acepta mediante la autenticación común, pero esos dos accesos no se pudieron comprobar con cuentas reales.

No hace falta ejecutar una migración para HU08.
