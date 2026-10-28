# Escenario variable v4 para HU02, HU03 y HU06

Este conjunto conserva el caso variable de v3 y corrige las etiquetas sintéticas para que se deriven de los atributos actuales. No consulta WUF ni representa adopciones reales. La versión v3 se conserva sin cambios para reproducir resultados anteriores.

| Captura | Fecha / semana ISO | Filas | Disponibles | No disponibles |
|---|---|---:|---:|---:|
| Inicial | 28/09/2026 · 40 | 180 | 108 | 72 |
| Seguimiento 1 | 05/10/2026 · 41 | 165 | 87 | 78 |
| Seguimiento 2 | 12/10/2026 · 42 | 190 | 86 | 104 |

## Transiciones preservadas

La cohorte inicial contiene 108 mascotas disponibles. El resultado esperado HU02 continúa siendo 66 `permanece` y 42 `salio_catalogo` (proxy):

- 10: `Disponible → No disponible → Sin registro`.
- 11: `Disponible → No disponible → No disponible`.
- 21: `Disponible → Disponible → No disponible`.

Las 72 mascotas no disponibles al inicio no pertenecen a la cohorte HU02. Los 35 SKU añadidos en la última captura tampoco pertenecen a la cohorte inicial.

## Etiquetas y valores ausentes

El generador [`scripts/generar_escenario_hu02_variable_v4.py`](../../../scripts/generar_escenario_hu02_variable_v4.py) vuelve a derivar `etiquetas` después de crear o modificar los atributos:

- `Cachorro`: edad numérica de hasta 11 meses, siguiendo las etiquetas del conjunto base.
- `Senior`: edad numérica de 96 meses o más. Para HU06, 8 años es un umbral provisional de demostración, no una definición veterinaria.
- `Condicion especial`: se incluye si `condicion_especial=true`; el detalle específico permanece en `condicion_detalle`.
- Si la edad es desconocida, `edad_meses` queda vacío, `edad_estimada=false` y no se inventa una etiqueta de edad. Si hay edad numérica estimada, se conserva `edad_estimada=true` y la etiqueta etaria correspondiente; HU06 puede marcarla como estimada.

Las etiquetas no participan en el entrenamiento HU03; se guardan como datos de perfil para mostrar y segmentar. HU03 usa `edad_meses`, `edad_estimada`, tamaño, condición y los demás atributos definidos en su pipeline. Por eso, la corrección de `edad_estimada` en registros sin edad puede cambiar ligeramente métricas o importancias de HU03; las etiquetas HU02 y las transiciones no cambian.

## Uso

Ejecuta desde la raíz del proyecto para regenerar exactamente esta versión:

```powershell
python scripts\generar_escenario_hu02_variable_v4.py
```

Importa las tres capturas manualmente y en orden cronológico. Como las fechas y nombres coinciden con los de otros escenarios, no mezcles v4 con datos v3 ya importados. Para probarlo, usa una base de demostración vacía o una base aislada destinada a esta versión; no vuelvas a ejecutar el esquema sobre una base que ya contiene datos.
