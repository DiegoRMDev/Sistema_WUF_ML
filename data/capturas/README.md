# Capturas CSV para HU01

Puedes organizar aquí las capturas de catálogo en archivos CSV UTF-8. El backend no lee esta carpeta automáticamente: el Analista selecciona manualmente el archivo que desea importar. Usa nombres descriptivos, por ejemplo `captura_2026-10-01.csv` y `captura_2026-10-08.csv`.

## Archivos de demostración incluidos

Se incluyen tres capturas semanales (`captura_demo_2026-09-28.csv`, `captura_demo_2026-10-05.csv` y `captura_demo_2026-10-12.csv`). Cada una contiene los mismos 60 SKU estables para que puedas importar primero la más antigua y luego las siguientes, y ver cómo se conserva el historial mientras `mascota` se actualiza. Hay cambios de estado y orden entre semanas.

Las 12 etiquetas positivas por archivo son **sintéticas**, asignadas de forma estable por SKU para probar HU02/HU03. No son datos de WUF ni adopciones confirmadas. Las capturas producen 180 observaciones, pero solo 60 mascotas independientes; al evaluar modelos, divide por SKU para evitar que observaciones de una misma mascota aparezcan a la vez en entrenamiento y evaluación.

Cada archivo representa una captura completa. Mantén el mismo `sku` para la misma mascota en todos los archivos. El backend actualiza `mascota` con la versión más reciente y conserva una fila independiente en `snapshot_catalogo` por ejecución.

## Encabezados requeridos

```csv
sku,nombre,especie,raza,sexo,edad_meses,edad_estimada,tipo_pelaje,tamano,tamano_estimado,nivel_energia,condicion_especial,condicion_detalle,descripcion,orden_publicacion,estado_publicado,fecha_publicacion,url_perfil,etiquetas,etiqueta_adoptado
```

- `edad_meses`, `condicion_detalle` y `descripcion` pueden estar vacíos.
- Booleanos: escribe `true` o `false`; no se aceptan variantes ambiguas.
- `sexo`: `M` o `H`; `especie`: `perro` o `gato`.
- `estado_publicado`: `disponible`, `no_disponible` o `sin_publicar`.
- `fecha_publicacion`: formato `AAAA-MM-DD`.
- `url_perfil`: HTTPS en `wuf.pe` o `www.wuf.pe`.
- `etiquetas`: lista separada por `|`; puede quedar vacía.
- `etiqueta_adoptado`: `true` o `false` sintético explícito. No significa adopción verificada y no crea filas en `adopcion`.

Puedes organizar tus CSV en esta carpeta, pero la API no la escanea: cada archivo se importa manualmente al seleccionarlo en la interfaz. El tamaño máximo se configura con `CATALOG_CSV_MAX_BYTES` en `backend/.env`. Los CSV se excluyen de Git. El mismo nombre se puede reintentar si la importación anterior falló; una importación exitosa o parcial no se repite.
