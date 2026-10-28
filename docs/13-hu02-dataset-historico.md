# HU02 — Dataset Histórico etiquetado

## Alcance de esta implementación

La pantalla consulta PostgreSQL y presenta la comparación semanal indicada por el prototipo: ID/SKU, mascota, orden de publicación, estados de cada captura y etiqueta final. El Analista elige las capturas inicial y final; ese rango define el horizonte de seguimiento (dos o más semanas completas) y genera una versión. Se requieren al menos tres capturas completas. La versión conserva su procedencia y hash SHA-256 en PostgreSQL; el hash se oculta en el resumen visual.

## Regla de cohorte y etiquetas

- Se usa como cohorte inicial cada mascota disponible en la primera captura completa. Los atributos de entrenamiento proceden de ese primer snapshot.
- Si una captura completa posterior informa `no_disponible`, la etiqueta final es `salio_catalogo` y se registra el primer snapshot de evidencia. RF03 lo interpreta como proxy, nunca como adopción verificada.
- Si la mascota permanece `disponible` en todas las capturas posteriores, queda `permanece` y se registra el último snapshot comparado.
- Si un perfil no aparece en una ejecución completa posterior, la ausencia es evidencia de salida. Si aparece `sin_publicar` antes de otra evidencia concluyente, queda `indeterminada`.
- Las mascotas que ya estaban `no_disponible` o `sin_publicar` en la referencia quedan fuera de la cohorte.
- Las fechas elegidas deben corresponder a ejecuciones completas, incluir al menos tres capturas y abarcar un mínimo de dos semanas completas. Capturas parciales/fallidas no entran al conjunto ni sirven para inferir ausencias.

## API e interfaz

- `GET /api/v1/datasets/sources`: ofrece capturas completadas al selector del periodo.
- `GET /api/v1/datasets`: lista versiones.
- `POST /api/v1/datasets`: recibe `fecha_desde` y `fecha_hasta`, valida los extremos y crea una versión solo con el periodo elegido. Requiere Analista.
- `GET /api/v1/datasets/{id}`: devuelve resumen, estados semanales y registros.
- `GET /api/v1/datasets/{id}/export`: CSV con atributos de referencia, secuencia semanal y etiqueta derivada.
- Todas las rutas aplican autenticación y autorización en backend. Los datos de la tabla son dinámicos; la maqueta estática no se usa como dato funcional.
- El buscador por SKU/nombre y el filtro por etiqueta solo cambian las filas visibles. El botón exporta el dataset completo, independientemente de los filtros.
- La tabla ofrece desplazamiento vertical y horizontal dentro de su contenedor.

## Escenarios demo y estado de validación

La base activa del proyecto es `wuf_predict_v6`; para las pruebas variables actuales se importan los tres CSV de `data/capturas/escenario_hu02_variable_v4/`. El caso `wuf_predict_v3` con `data/capturas/escenario_hu02_v3/` corresponde a una prueba anterior de 180 perfiles estables y se conserva solo como referencia. En ambos casos, HU02 deriva las etiquetas de los snapshots y no añade una etiqueta sintética de adopción.

El escenario variable original `data/capturas/escenario_hu02_variable_v3/` contiene 180→165→190 perfiles y se conserva para reproducir pruebas anteriores. La versión corregida `data/capturas/escenario_hu02_variable_v4/` mantiene 10 casos `disponible → no_disponible → sin registro`, 11 `disponible → no_disponible → no_disponible` y 21 `disponible → disponible → no_disponible`; 66 permanecen disponibles. En ambos conjuntos, los 15 perfiles no disponibles en la referencia que faltan en semana 41 y los 35 SKU nuevos de semana 42 están fuera de la cohorte de entrenamiento. V4 regenera las etiquetas sintéticas de edad/condición y corrige los indicadores de edad ausente; no cambia las transiciones ni las etiquetas derivadas por HU02. Sus detalles y el generador están en el [README v4](../data/capturas/escenario_hu02_variable_v4/README.md) y [`scripts/generar_escenario_hu02_variable_v4.py`](../scripts/generar_escenario_hu02_variable_v4.py).

Los CSV variables pasan el contrato HU01 sin rechazos y la regla de dominio produce 108 filas, 66 `permanece` y 42 `salio_catalogo`. El usuario confirmó que probó la última versión en la interfaz y que el resultado fue correcto. Para repetir la prueba después de haber importado una versión anterior con esos mismos nombres, se requiere una base demo vacía nueva. No se necesita migración ni cambio de esquema.

## Auditoría de filas indeterminadas y relación con HU03

La decisión acordada conserva la trazabilidad sin tratar una etiqueta incierta como verdad de entrenamiento:

- **Exportación HU02:** incluir todos los registros, también `indeterminada`, con `motivo_indeterminado`. La exportación representa el historial completo y auditable.
- **Interfaz HU02:** mostrar el motivo junto a la etiqueta `Indeterminada` cuando exista una fila de esa clase. El resumen mantiene el conteo de indeterminadas.
- **Entrenamiento HU03:** al cargar el CSV, excluir del entrenamiento las filas `indeterminada`; preservar el archivo original sin alterarlo.

Los CSV controlados actuales no contienen `sin_publicar` y se mantienen así para conservar el escenario acordado. La interfaz queda preparada para mostrar el motivo si aparece una fila indeterminada en una captura futura; el backend lo entrega en los detalles y lo incluye en el CSV.

HU03 registra el balance de clases, separa por SKU para evitar fuga y presenta las métricas del escenario como demostrativas: la salida del catálogo es un proxy, no una adopción verificada. Consulta [`14-hu03-entrenamiento-modelo.md`](14-hu03-entrenamiento-modelo.md) para el proceso de entrenamiento.
