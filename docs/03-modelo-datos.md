# Modelo físico y diccionario de datos

Este documento conserva el diccionario del modelo físico del avance y registra las extensiones mínimas para HU01. [`../backend/schema.sql`](../backend/schema.sql) sirve para instalaciones nuevas; los archivos `upgrade_*.sql` actualizan bases ya creadas sin eliminar sus registros.

## Diccionario de datos

En la columna **Restricción** se conserva `PK`, `FK`, `NOT NULL` y `NULL` según el diccionario. En PostgreSQL, `SERIAL` genera una secuencia para el identificador; `PRIMARY KEY` implica `NOT NULL`.

### mascota

| Columna | Tipo | Restricción |
|---|---|---|
| id_mascota | SERIAL | PK, NOT NULL |
| sku | VARCHAR(10) | NOT NULL, UNIQUE (identidad estable entre capturas) |
| nombre | VARCHAR(80) | NOT NULL |
| especie | VARCHAR(10) | NOT NULL |
| raza | VARCHAR(30) | NOT NULL |
| sexo | CHAR(1) | NOT NULL |
| edad_meses | INTEGER | NULL |
| edad_estimada | BOOLEAN | NOT NULL |
| tipo_pelaje | VARCHAR(15) | NOT NULL |
| tamano | VARCHAR(10) | NOT NULL |
| tamano_estimado | BOOLEAN | NOT NULL |
| nivel_energia | VARCHAR(10) | NOT NULL |
| condicion_especial | BOOLEAN | NOT NULL |
| condicion_detalle | VARCHAR(200) | NULL |
| descripcion | VARCHAR(512) | NULL |
| orden_publicacion | INTEGER | NOT NULL |
| estado_publicado | VARCHAR(20) | NOT NULL |
| fecha_publicacion | DATE | NOT NULL |
| url_perfil | VARCHAR(255) | NOT NULL |

### etiqueta_condicion

| Columna | Tipo | Restricción |
|---|---|---|
| id_etiqueta | SERIAL | PK, NOT NULL |
| id_mascota | INTEGER | FK → mascota, NOT NULL |
| etiqueta | VARCHAR(30) | NOT NULL |

### adopcion

| Columna | Tipo | Restricción |
|---|---|---|
| id_adopcion | SERIAL | PK, NOT NULL |
| id_mascota | INTEGER | FK → mascota, NOT NULL |
| id_adoptante | INTEGER | FK → adoptante, NOT NULL |
| fecha_adopcion | DATE | NOT NULL |
| costo | DECIMAL(8,2) | NOT NULL |
| estado | VARCHAR(20) | NOT NULL |

### adoptante

| Columna | Tipo | Restricción |
|---|---|---|
| id_adoptante | SERIAL | PK, NOT NULL |
| nombre | VARCHAR(100) | NOT NULL |
| email | VARCHAR(100) | NOT NULL |
| telefono | VARCHAR(20) | NOT NULL |

### snapshot_catalogo

| Columna | Tipo | Restricción |
|---|---|---|
| id_snapshot | SERIAL | PK, NOT NULL |
| id_mascota | INTEGER | FK → mascota, NOT NULL |
| id_dataset | INTEGER | FK → dataset_historico, NULL |
| id_ejecucion | INTEGER | FK → ejecucion_recoleccion, NOT NULL en instalación nueva |
| semana | INTEGER | NOT NULL |
| fecha_captura | TIMESTAMP | NOT NULL |
| sku | VARCHAR(10) | NOT NULL |
| nombre | VARCHAR(80) | NOT NULL |
| especie | VARCHAR(10) | NOT NULL |
| raza | VARCHAR(30) | NOT NULL |
| sexo | CHAR(1) | NOT NULL |
| edad_meses | INTEGER | NULL |
| edad_estimada | BOOLEAN | NOT NULL |
| tipo_pelaje | VARCHAR(15) | NOT NULL |
| tamano | VARCHAR(10) | NOT NULL |
| tamano_estimado | BOOLEAN | NOT NULL |
| nivel_energia | VARCHAR(10) | NOT NULL |
| condicion_especial | BOOLEAN | NOT NULL |
| condicion_detalle | VARCHAR(200) | NULL |
| descripcion | VARCHAR(512) | NULL |
| orden_publicacion | INTEGER | NOT NULL |
| estado_detectado | VARCHAR(20) | NOT NULL |
| fecha_publicacion | DATE | NOT NULL |
| url_perfil | VARCHAR(255) | NOT NULL |
| etiqueta_adoptado | BOOLEAN | NULL o etiqueta sintética explícita de la captura |
| origen_etiqueta | VARCHAR(20) | NULL; `sintetica`, `verificada`, `inferida` o `desconocida` |

### snapshot_etiqueta_condicion (extensión HU01)

Conserva las etiquetas múltiples observadas en cada captura, separadas de las etiquetas actuales de la mascota.

| Columna | Tipo | Restricción |
|---|---|---|
| id_snapshot | INTEGER | PK compuesta, FK → snapshot_catalogo, NOT NULL |
| etiqueta | VARCHAR(30) | PK compuesta, NOT NULL |

### alerta_desactualizacion

| Columna | Tipo | Restricción |
|---|---|---|
| id_alerta | SERIAL | PK, NOT NULL |
| id_mascota | INTEGER | FK → mascota, NOT NULL |
| fecha | TIMESTAMP | NOT NULL |
| nivel_riesgo | VARCHAR(10) | NOT NULL |
| mensaje | VARCHAR(255) | NOT NULL |
| estado | VARCHAR(15) | NOT NULL |

### prediccion

| Columna | Tipo | Restricción |
|---|---|---|
| id_prediccion | SERIAL | PK, NOT NULL |
| id_modelo | INTEGER | FK → modelo_predictivo, NOT NULL |
| id_mascota | INTEGER | FK → mascota, NOT NULL |
| id_reporte | INTEGER | FK → reporte_priorizacion, NULL |
| probabilidad_adopcion | DECIMAL(5,4) | NOT NULL |
| nivel_prioridad | VARCHAR(10) | NOT NULL |
| fecha | TIMESTAMP | NOT NULL |

### reporte_priorizacion

| Columna | Tipo | Restricción |
|---|---|---|
| id_reporte | SERIAL | PK, NOT NULL |
| id_usuario | INTEGER | FK → usuario, NOT NULL |
| semana | INTEGER | NOT NULL |
| fecha_generacion | TIMESTAMP | NOT NULL |
| formato | VARCHAR(10) | NOT NULL |

### dataset_historico

| Columna | Tipo | Restricción |
|---|---|---|
| id_dataset | SERIAL | PK, NOT NULL |
| fecha_generacion | TIMESTAMP | NOT NULL |
| nro_registros | INTEGER | NOT NULL |
| version | VARCHAR(10) | NOT NULL |
| origen_etiquetas | VARCHAR(20) | NOT NULL; `sintetica`, `verificada`, `inferida`, `mixta` o `desconocida` |

### ejecucion_recoleccion (extensión HU01)

Registra las ejecuciones manuales por CSV y los contadores mostrados en la pantalla de recolección. El esquema conserva el campo de tipo para compatibilidad del modelo, pero no hay un programador activo en la implementación actual.

| Columna | Tipo | Restricción |
|---|---|---|
| id_ejecucion | SERIAL | PK, NOT NULL |
| id_usuario | INTEGER | FK → usuario, NULL permitido por compatibilidad con ejecuciones del sistema |
| tipo_ejecucion | VARCHAR(15) | NOT NULL |
| fuente_datos | VARCHAR(24) | NOT NULL, DEFAULT `csv_simulada` |
| referencia_fuente | VARCHAR(255) | NULL; nombre del CSV procesado |
| fecha_inicio | TIMESTAMP | NOT NULL |
| fecha_fin | TIMESTAMP | NULL |
| semana | INTEGER | NOT NULL |
| perfiles_total | INTEGER | NOT NULL, DEFAULT 0 |
| perfiles_disponibles | INTEGER | NOT NULL, DEFAULT 0 |
| perfiles_no_disponibles | INTEGER | NOT NULL, DEFAULT 0 |
| perfiles_sin_publicar | INTEGER | NOT NULL, DEFAULT 0 |
| estado | VARCHAR(15) | NOT NULL |
| mensaje_error | VARCHAR(1000) | NULL |

### modelo_predictivo

| Columna | Tipo | Restricción |
|---|---|---|
| id_modelo | SERIAL | PK, NOT NULL |
| id_dataset | INTEGER | FK → dataset_historico, NOT NULL |
| algoritmo | VARCHAR(30) | NOT NULL |
| version | VARCHAR(10) | NOT NULL |
| accuracy_score | DECIMAL(5,4) | NOT NULL |
| precision_score | DECIMAL(5,4) | NOT NULL |
| recall_score | DECIMAL(5,4) | NOT NULL |
| f1_score | DECIMAL(5,4) | NOT NULL |
| fecha_entrenamiento | TIMESTAMP | NOT NULL |

### usuario

| Columna | Tipo | Restricción |
|---|---|---|
| id_usuario | SERIAL | PK, NOT NULL |
| nombre | VARCHAR(100) | NOT NULL |
| rol | VARCHAR(20) | NOT NULL |
| email | VARCHAR(100) | NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL |

## Relaciones documentadas

- `etiqueta_condicion.id_mascota` referencia `mascota.id_mascota`.
- `adopcion.id_mascota` referencia `mascota.id_mascota`; `adopcion.id_adoptante` referencia `adoptante.id_adoptante`.
- `snapshot_catalogo.id_mascota` referencia `mascota.id_mascota`; `snapshot_catalogo.id_dataset` referencia `dataset_historico.id_dataset` y admite NULL.
- `snapshot_catalogo.id_ejecucion` referencia `ejecucion_recoleccion.id_ejecucion`.
- `ejecucion_recoleccion.id_usuario` referencia `usuario.id_usuario`; admite NULL por compatibilidad de datos históricos.
- `snapshot_etiqueta_condicion.id_snapshot` referencia `snapshot_catalogo.id_snapshot`; su clave primaria compuesta es (`id_snapshot`, `etiqueta`).
- `alerta_desactualizacion.id_mascota` referencia `mascota.id_mascota`.
- `prediccion.id_modelo` referencia `modelo_predictivo.id_modelo`; `prediccion.id_mascota` referencia `mascota.id_mascota`; `prediccion.id_reporte` referencia `reporte_priorizacion.id_reporte` y admite NULL.
- `reporte_priorizacion.id_usuario` referencia `usuario.id_usuario`.
- `modelo_predictivo.id_dataset` referencia `dataset_historico.id_dataset`.

## Orden de creación

El SQL crea primero las tablas referenciadas y luego sus dependientes: usuario y mascota; adoptante, dataset y ejecución; posteriormente relaciones, snapshots, etiquetas históricas, modelos, reportes y predicciones.

## Complicaciones y límites del modelo definido

El esquema se ajusta al diccionario; estos puntos describen capacidades que el diccionario no modela y no se han resuelto añadiendo campos:

1. **Snapshots anteriores:** las migraciones dejan nullable las columnas nuevas para conservar filas ya creadas. No las rellenan con los valores actuales de `mascota`, porque eso falsearía el historial.
2. **Etiqueta de adopción:** el CSV entrega explícitamente `true`/`false` sintético; HU01 lo guarda con `origen_etiqueta='sintetica'`. No es evidencia de adopción real ni crea filas en `adopcion`. HU02 debe copiar la procedencia a `dataset_historico.origen_etiquetas`; HU03 limita datasets sintéticos a experimentos y requiere `verificada` para activación operativa.

3. **Calidad de CSV:** se validan encabezados exactos, codificación UTF-8, tamaño, dominios, tipos y SKU duplicados. Los perfiles inválidos se rechazan con un resumen; no se generan valores para completar campos obligatorios.
4. **Vinculación snapshot-dataset:** cada snapshot tiene como máximo un `id_dataset` en esta estructura, que además puede ser nulo. Si se necesita reutilizar una captura en varias versiones de dataset, el modelo actual no representa esa relación.
5. **Seguimiento de alertas:** la tabla guarda fecha, riesgo, mensaje y estado, pero no registra quién atendió la alerta, cuándo ni una nota de resolución. El flujo de HU07 quedaría limitado a cambiar `estado` salvo que se revise el diccionario.
6. **Control de unicidad y dominios:** el diccionario no enumera dominios para estado, sexo, rol, formato y prioridad. La aplicación debe validar esos valores; los `CHECK` añadidos se limitan a rangos numéricos, fechas, estado/origen de las ejecuciones y completitud de snapshots nuevos.
7. **Identidad/idempotencia:** `UNIQUE (sku)` identifica una mascota entre ejecuciones y `UNIQUE (id_ejecucion, id_mascota)` impide duplicarla dentro de una captura. Los CSV deben conservar el SKU para el mismo animal y no reutilizarlo para otro. Cada nombre de archivo se consume una vez. La migración CSV crea el índice único; si hay SKU duplicados existentes, hay que resolverlos antes.
8. **Ejecuciones de recolección:** HU01 puede registrar tipo, inicio/fin, semana, conteos, estado, error y usuario iniciador. “Vigente” se deriva de la última ejecución completada, no se almacena como estado.
9. **Importación CSV:** el Analista selecciona cada archivo y lo envía manualmente. Un archivo exitoso o parcial no se puede repetir con el mismo nombre; uno fallido se puede corregir y reintentar.
10. **Artefactos y parámetros ML:** `modelo_predictivo` registra algoritmo, versión, métricas y fecha, pero no ubicación del archivo entrenado, parámetros, semilla, partición ni cuál modelo está activo.
11. **Datos personales:** `adoptante` contiene nombre, email y teléfono. El acceso debe limitarse y estos datos no deben incluirse como variables del modelo.

El archivo `schema.sql` crea el modelo físico documentado y las extensiones de HU01 para una instalación nueva. No incluye datos semilla ni capturas CSV.

## Actualizar una base ya creada

Si la base `wuf_predict` ya se creó con una versión anterior, **no vuelvas a ejecutar `schema.sql`**. Haz una copia de seguridad y aplica en orden las migraciones que falten: `upgrade_hu01.sql`, `upgrade_hu01_etiqueta.sql`, `upgrade_hu01_simulacion.sql` y finalmente [`../backend/upgrade_hu01_csv.sql`](../backend/upgrade_hu01_csv.sql). La última elimina ejecuciones sin snapshots asociados para limpiar intentos de prueba vacíos; conserva ejecuciones con historial, agrega referencia del archivo y procedencia de etiquetas/datasets, y cambia el origen predeterminado a CSV. La procedencia de etiquetas y datasets anteriores queda como `desconocida`.

Las filas previas de `snapshot_catalogo` mantienen NULL en atributos históricos y `id_ejecucion` cuando no se pudieron reconstruir. La restricción `ck_snapshot_hu01_completo` conserva esa compatibilidad. HU01 crea primero una ejecución y luego guarda atributos, etiquetas de condición y procedencia de etiqueta en cada snapshot.

## Restricciones CHECK añadidas

Estas restricciones no cambian columnas ni relaciones; rechazan valores que no son válidos según su significado. Los límites categóricos (por ejemplo, valores permitidos para estado, rol, especie o prioridad) siguen sin restringirse porque el diccionario no enumera sus dominios.

| Tabla | Restricción | Regla |
|---|---|---|
| mascota | `ck_mascota_edad_meses_no_negativa` | `edad_meses` puede ser NULL; si tiene valor debe ser >= 0 |
| mascota | `ck_mascota_orden_publicacion_positivo` | `orden_publicacion` debe ser > 0 |
| adopcion | `ck_adopcion_costo_no_negativo` | `costo` debe ser >= 0 |
| dataset_historico | `ck_dataset_nro_registros_no_negativo`, `ck_dataset_origen_etiquetas` | Conteo no negativo y procedencia reconocida |
| snapshot_catalogo | `ck_snapshot_semana` | `semana` debe estar entre 1 y 53 |
| modelo_predictivo | `ck_modelo_metricas_rango` | Accuracy, Precision, Recall y F1 deben estar entre 0 y 1 |
| reporte_priorizacion | `ck_reporte_semana` | `semana` debe estar entre 1 y 53 |
| prediccion | `ck_prediccion_probabilidad_rango` | `probabilidad_adopcion` debe estar entre 0 y 1 |
| ejecucion_recoleccion | `ck_ejecucion_tipo`, `ck_ejecucion_fuente_datos`, `ck_ejecucion_estado`, `ck_ejecucion_semana`, `ck_ejecucion_conteos`, `ck_ejecucion_fechas` | En esquema nuevo se usa `csv_simulada`; conserva validaciones de semana, conteos y fechas |
| ejecucion_recoleccion | `uq_ejecucion_csv_referencia` | El mismo archivo CSV no se procesa dos veces |
| snapshot_catalogo | `ck_snapshot_origen_etiqueta` | La etiqueta y su procedencia se guardan juntas |
| snapshot_catalogo | `ck_snapshot_edad_meses_no_negativa`, `ck_snapshot_orden_publicacion_positivo` | Edad no negativa (o NULL) y orden positivo |
| snapshot_catalogo (migración) | `ck_snapshot_hu01_completo` | Si el snapshot está asociado a ejecución, exige los atributos requeridos; se agrega `NOT VALID` para conservar filas antiguas |
