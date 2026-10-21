# Escenario HU02/HU03 con capturas variables

Estos CSV sintéticos y reproducibles sirven para practicar la importación HU01, la comparación HU02 y el entrenamiento HU03. El generador es [`scripts/generar_escenario_hu02_variable.py`](../../../scripts/generar_escenario_hu02_variable.py). No consulta WUF ni representa adopciones reales.

| Captura | Fecha / semana ISO | Filas | Disponibles | No disponibles | Cambio incluido |
|---|---|---:|---:|---:|---|
| Inicial | 28/09/2026 · 40 | 180 | 108 | 72 | Cohorte inicial de 108 perfiles disponibles |
| Seguimiento 1 | 05/10/2026 · 41 | 165 | 87 | 78 | 21 de la cohorte cambian a `no_disponible`; 15 perfiles que ya estaban no disponibles dejan de aparecer |
| Seguimiento 2 | 12/10/2026 · 42 | 190 | 86 | 104 | 10 de la cohorte desaparecen después de una semana no disponibles; 11 permanecen no disponibles; 21 cambian en esta captura; se agregan 35 perfiles nuevos |

## Etiquetas y supuestos de demostración

- HU02 conserva 108 registros de la cohorte inicial: 66 `permanece` y 42 `salio_catalogo` (proxy). El flujo de los 42 casos es 10 `Disponible → No disponible → Sin registro`, 11 `Disponible → No disponible → No disponible` y 21 `Disponible → Disponible → No disponible`.
- Los perfiles que ingresan en la semana 42 quedan en sus snapshots, pero no pertenecen a la cohorte inicial y no se agregan al dataset HU02 de ese periodo.
- Para que HU03 pueda mostrar cómo aprende de atributos, el generador asigna una propensión sintética moderada a la salida del catálogo: menor edad, tamaño pequeño y ausencia de condición especial la elevan. Se añade variación aleatoria para que atributos parecidos puedan terminar en etiquetas distintas. Raza, sexo, pelaje y energía no se usan para asignar esa propensión.
- Esos supuestos sirven para explicar el algoritmo y observar asociaciones en una muestra pequeña. No demuestran qué factores causan una adopción real. `salio_catalogo` no confirma adopción; puede representar otros cambios administrativos o una ficha retirada.
- Los nombres de las altas son nombres plausibles de mascotas y permanecen iguales en todas las capturas donde aparece el mismo SKU. Todo el contenido y los perfiles continúan siendo sintéticos.

## Resultado de una ejecución de referencia

Con 100 árboles, profundidad máxima 10, 30 % para prueba y semilla 42, el código actual de HU03 produjo Accuracy 81,8 %, Precision 80,0 %, Recall 66,7 %, F1 72,7 % y matriz `[[19, 2], [4, 8]]`. En la importancia One-Hot destacaron edad (34,5 %), orden de publicación (10,4 %), condición especial (10,0 %) y categorías de tamaño pequeño/grande (4,3 % y 4,2 %). Son resultados de una sola partición de datos sintéticos; pueden cambiar si varían los CSV, la semilla o los parámetros. La importancia es una señal predictiva del bosque, no una relación causal.

## Importación

Importa las tres capturas en orden cronológico desde HU01. Genera el dataset HU02 entre el 28/09 y el 12/10 y revisa los conteos esperados. Como el backend impide volver a importar correctamente el mismo nombre en una base que ya lo contiene, usa una base de demostración vacía. La importación actualiza `mascota` y agrega snapshots; una base aislada evita mezclar el escenario con otras capturas.

Para reproducir los archivos desde la raíz del proyecto:

```powershell
python scripts\generar_escenario_hu02_variable.py
```

El generador conserva el flujo y los conteos semanales y usa una semilla fija para que la misma versión del código produzca los mismos CSV. El contrato de importación HU01 aceptó las tres capturas con cero perfiles rechazados.
