# Escenario HU02 con cantidades variables

Este conjunto sintético y reproducible sirve para probar altas, cambios de estado y salidas por ausencia. Se genera desde los perfiles base con `scripts/generar_escenario_hu02_variable.py`; no consulta WUF ni modifica `escenario_hu02_v3`.

| Captura | Fecha / semana ISO | Filas | Disponibles | No disponibles | Cambio incluido |
|---|---|---:|---:|---:|---|
| Inicial | 28/09/2026 · 40 | 180 | 108 | 72 | Cohorte inicial de 108 mascotas disponibles |
| Seguimiento 1 | 05/10/2026 · 41 | 165 | 87 | 78 | 21 de la cohorte pasan a `no_disponible`; 15 perfiles ya no disponibles dejan de aparecer |
| Seguimiento 2 | 12/10/2026 · 42 | 190 | 86 | 104 | 10 desaparecen tras una semana `no_disponible`; 11 siguen así; 21 cambian recién ahora; se agregan 35 SKU nuevos |

## Resultado HU02 esperado

- Cohorte inicial: 108 perfiles disponibles en semana 40.
- `salio_catalogo`: 42, distribuidos en tres flujos: 10 pasan de `disponible` a `no_disponible` y luego a `sin registro`; 11 pasan a `no_disponible` y permanecen así; 21 siguen disponibles en semana 41 y pasan a `no_disponible` en semana 42.
- `permanece`: 66 (disponibles hasta la captura final).
- Los 15 perfiles que desaparecen en semana 41 ya estaban `no_disponible` en la referencia y no pertenecen a la cohorte. Por tanto, ninguna mascota de la cohorte inicial desaparece directamente desde `disponible`.
- Los 35 SKU nuevos de semana 42 quedan guardados en los snapshots de esa captura, pero no pertenecen a la cohorte inicial: no se convierten en filas del dataset ni aumentan sus 108 registros.
- No se incluyen capturas parciales/fallidas; no se agrega `etiqueta_adoptado`. “Salió del catálogo” sigue siendo un proxy y no confirma adopción.

## Importación segura

Importa las tres capturas en orden cronológico desde la interfaz HU01, genera el dataset entre el 28/09 y el 12/10 y comprueba los conteos esperados. Usa una base de datos de demostración vacía basada en `backend/schema_wuf_predict_v2.sql` (por ejemplo, `wuf_predict_hu02_variable_v2` si aún no la usaste; de lo contrario, crea otra con un nombre nuevo). Como ya se importó una versión anterior de estos archivos, no vuelvas a importarlos en la base que usaste para aquella prueba: el backend impide repetir nombres que ya se importaron correctamente. La base nueva también evita:

1. Los nombres/fechas coinciden con las capturas del escenario controlado y HU01 no permite reimportar con éxito el mismo nombre en una base que ya las contiene.
2. Cada importación también actualiza los datos vigentes de `mascota`; una base aislada evita mezclar este escenario alternativo con las capturas de v3.

Después de crear y preparar la base aislada, apunta temporalmente `DATABASE_URL` del backend a ella, reinicia la API, crea ahí un usuario Analista e importa estos tres archivos. Para volver al entorno normal, restaura `DATABASE_URL` hacia `wuf_predict_v3` y reinicia la API. No se necesita migración nueva.

## Reproducir archivos

Desde la raíz del proyecto:

```powershell
python scripts\generar_escenario_hu02_variable.py
```

El generador comprueba los conteos estructurales antes de escribir. Los CSV resultantes se validaron con el mismo adaptador/contrato de importación de HU01: cero perfiles rechazados en las tres capturas.
