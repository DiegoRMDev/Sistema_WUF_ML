# Pendiente HU02 — ampliar variación temporal de los CSV demo

## Estado

Pendiente para el módulo HU02. Los tres archivos actuales se conservan como conjunto base para probar la importación y la consulta del historial:

- `captura_demo_2026-09-28.csv`
- `captura_demo_2026-10-05.csv`
- `captura_demo_2026-10-12.csv`

Cada captura contiene 180 SKU. Los SKU se mantienen entre semanas y cada perfil conserva el mismo estado en las tres capturas (108 `disponible`, 72 `no_disponible`). Por ello, el conjunto demuestra persistencia de snapshots, pero todavía no cubre transiciones temporales ni altas y ausencias entre capturas.

## Trabajo pendiente

Al implementar HU02, preparar una variante demostrativa de los CSV que agregue cambios controlados, manteniendo la identidad estable por SKU. Evaluar ambos escenarios:

1. **Cambio de estado:** algunos perfiles pasan de `disponible` a `no_disponible` o viceversa entre fechas.
2. **Cambio en cantidad:** algunas mascotas aparecen o dejan de aparecer en capturas posteriores; no es necesario que todos los archivos tengan 180 filas.

La primera prueba de HU02 puede seguir usando 180 filas por semana para verificar el caso pareado. La variante debe representar capturas completas; una fila ausente solo puede interpretarse como salida si la captura posterior está marcada como completa. Una captura parcial o fallida no debe etiquetar ausencias como salidas.

## Criterios para generar la variante

- Conservar SKU en perfiles que representan a la misma mascota; nunca reutilizar un SKU para otra.
- Mantener fechas válidas y usar las semanas ISO derivadas del nombre del archivo.
- Registrar con claridad qué filas/estados cambiaron y por qué, de forma reproducible.
- Mantener valores dentro del contrato CSV y no agregar una columna `etiqueta_adoptado` sintética.
- Conservar la semántica acordada con el prototipo: `disponible` → “Permanece”; `no_disponible` → “Salió del catálogo” como proxy, no como adopción verificada. `sin_publicar` o evidencia insuficiente queda indeterminada.
- Revisar el balance de clases y contar perfiles sin evidencia suficiente antes de usar el dataset en HU03.
- Evitar fuga temporal al entrenar: dividir por SKU o por tiempo, no repartir snapshots de una misma mascota entre entrenamiento y prueba sin control.

## Efecto previsto en los módulos

- **HU02:** permite verificar comparación entre semanas, salidas, cambios de estado y perfiles ausentes.
- **HU03:** aporta más ejemplos temporales; las métricas seguirán siendo demostrativas porque los datos son sintéticos y la salida del catálogo no confirma adopción.
- **HU04/HU07:** permite probar reglas de consistencia, riesgo y alertas ante cambios o ausencia, sin atribuirlos a datos reales.
- **HU05/HU06/HU08:** habilita reportes, segmentación y tendencias semanales con mayor variación; los resultados deben identificarse como demo.

## Efecto previsto en la base de datos

La variación semanal cabe en el diseño v2 existente: cada importación guarda una ejecución y sus snapshots; `mascota` conserva el estado vigente y los snapshots conservan los estados históricos. Las filas ausentes no generan snapshots en esa ejecución. HU02 debe asociar al dataset todas las ejecuciones consideradas para distinguir una ausencia real de una fecha sin captura. No se propone alterar el esquema solo para aumentar o variar las filas de los CSV.

Este pendiente no cambia los CSV actuales ni la base de datos. Se retoma al comenzar HU02 y se decide entonces cuántos perfiles variarán, qué transiciones se simularán y cómo documentar la integridad de cada captura completa.
