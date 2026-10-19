# Escenario controlado para HU02 (base limpia v3)

Este conjunto es una variante separada de `data/capturas/`; no modifica los tres CSV base de HU01 ni se debe importar en `wuf_predict_v2`.

## Archivos y resultado esperado

| Fecha de captura | Filas | disponibles | no_disponible | Uso |
|---|---:|---:|---:|---|
| 2026-09-28 | 180 | 108 | 72 | Captura de referencia; cohorte inicial de 108 disponibles |
| 2026-10-05 | 180 | 87 | 93 | 21 perfiles de la cohorte cambian a no disponible |
| 2026-10-12 | 180 | 66 | 114 | Otros 21 perfiles cambian a no disponible |

La cohorte HU02 se define por las mascotas disponibles en la primera captura. La salida posterior se etiqueta `salio_catalogo` (proxy del RF03, no prueba de adopción); las que continúan disponibles al cierre se etiquetan `permanece`. Resultado esperado: 66 permanecen y 42 salieron. Las 72 mascotas no disponibles desde la referencia no forman parte de la cohorte de entrenamiento.

Los perfiles y atributos se mantienen estables por SKU. No se añade `etiqueta_adoptado`; la etiqueta se deriva de los snapshots. Los archivos representan capturas completas de demostración.

## Orden de importación

Importa desde la interfaz HU01 en orden cronológico: 28/09, 05/10 y 12/10. Genera el dataset desde la sección Dataset histórico después de que las tres ejecuciones figuren como completadas. Para evitar mezclar datos, importa estos archivos únicamente en una base vacía `wuf_predict_v3`.

## Mejora posterior pendiente

Después de validar este caso pareado, se propone otro escenario con cantidades distintas por captura (por ejemplo, 180, 165 y 190 filas). Para ese caso HU02 debe consultar la ejecución completa como evidencia: una ausencia en una captura completa posterior puede significar salida del catálogo; una ejecución parcial/fallida no permite inferir salida. Los 3 archivos de esta primera prueba permanecen con 180 perfiles cada uno.
