# Capturas CSV para HU01

Puedes organizar aquí las capturas de catálogo en archivos CSV UTF-8. El backend no lee esta carpeta automáticamente: el Analista selecciona manualmente el archivo que desea importar. Usa nombres descriptivos, por ejemplo `captura_2026-10-01.csv` y `captura_2026-10-08.csv`.

## Archivos de demostración incluidos

Se incluyen tres capturas de demostración con fechas en el nombre (`captura_demo_2026-09-28.csv`, `captura_demo_2026-10-05.csv` y `captura_demo_2026-10-12.csv`). Cada archivo contiene 180 SKU estables (540 observaciones en total y 180 mascotas independientes), con distribución inspirada en la tabla de Dataset Histórico del prototipo. Cada semana contiene 108 perfiles `disponible` y 72 `no_disponible`. Para esta primera tanda se mantuvo el estado fijo por SKU en las tres fechas; así se prueba el historial, aunque aún no hay transiciones de estado entre semanas. Los datos y nombres son sintéticos; no se obtuvieron de WUF.

La fecha de captura se valida desde el nombre del archivo. Las fechas corresponden a semanas ISO 40, 41 y 42 de 2026. No se incluye `etiqueta_adoptado`: HU02 derivará “Permanece / Salió del catálogo” a partir de estados sucesivos, siguiendo el prototipo. La clase “Salió” es una aproximación del requisito original y no confirma adopción real.

Para probar cantidades variables, altas y ausencias sin alterar este conjunto ni mezclar historial, consulta [`escenario_hu02_variable_v3/README.md`](escenario_hu02_variable_v3/README.md). Ese escenario requiere una base de demostración aislada porque utiliza las mismas fechas y nombres de archivo que el conjunto de 180 filas.

Cada archivo representa una captura completa. Mantén el mismo `sku` para la misma mascota en todos los archivos. El backend actualiza `mascota` con la versión más reciente y conserva una fila independiente en `snapshot_catalogo` por ejecución.

## Encabezados requeridos

```csv
sku,nombre,especie,raza,sexo,edad_meses,edad_estimada,tipo_pelaje,tamano,tamano_estimado,nivel_energia,condicion_especial,condicion_detalle,descripcion,orden_publicacion,estado_publicado,fecha_publicacion,url_perfil,etiquetas
```

- `edad_meses`, `condicion_detalle` y `descripcion` pueden estar vacíos.
- Booleanos: escribe `true` o `false`; no se aceptan variantes ambiguas.
- `sexo`: `M` o `H`; `especie`: `perro` o `gato`.
- `estado_publicado`: `disponible`, `no_disponible` o `sin_publicar`.
- `fecha_publicacion`: formato `AAAA-MM-DD`.
- `url_perfil`: HTTPS en `wuf.pe` o `www.wuf.pe`.
- `etiquetas`: lista separada por `|`; puede quedar vacía.
- `etiqueta_adoptado`: ya no es requerido. Si un CSV antiguo aún lo incluye, el backend lo acepta por compatibilidad y descarta su valor; HU02 genera su propia etiqueta a partir de los snapshots.

Usa el patrón `captura_AAAA-MM-DD.csv` o `captura_demo_AAAA-MM-DD.csv`; la fecha debe ser válida y no futura. Puedes guardar los CSV en esta carpeta, pero la API no la escanea: cada archivo se importa manualmente desde la interfaz. El tamaño máximo se configura con `CATALOG_CSV_MAX_BYTES` en `backend/.env`. Los CSV de demostración están versionados en Git. El mismo nombre se puede reintentar si la importación anterior falló; una importación exitosa o parcial no se repite.
