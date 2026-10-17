# Modelo físico y diccionario de datos

Este documento conserva el diccionario físico del avance y diferencia el esquema actualmente usado del diseño v2 para HU02. [`../backend/schema.sql`](../backend/schema.sql) corresponde a la base anterior; [`../backend/schema_wuf_predict_v2.sql`](../backend/schema_wuf_predict_v2.sql) crea el esquema objetivo en una base vacía `wuf_predict_v2`. El SQL v2 no migra ni elimina datos de `wuf_predict`.

## Diccionario de datos del esquema anterior

Las tablas siguientes documentan el diccionario del avance y las extensiones HU01 actualmente usadas por `backend/schema.sql`. Más abajo se describen explícitamente las diferencias del esquema v2 para que no se confundan ambos contratos.

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
| semana | INTEGER | NOT NULL; semana ISO de la fecha representada por la captura |
| fecha_captura | TIMESTAMP | NOT NULL; instante/fecha de los datos capturados, no el de importación |
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
| etiqueta_adoptado | BOOLEAN | NULL; campo heredado opcional, no se persiste desde CSV ni se usa como clase HU02 |
| origen_etiqueta | VARCHAR(20) | NULL; campo heredado, permanece NULL en las capturas actuales |

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
| semana | INTEGER | NOT NULL; semana ISO de la captura importada |
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
2. **Etiqueta HU02:** el importador no requiere ni persiste `etiqueta_adoptado`; si un archivo legado contiene la columna, se valida y se descarta. HU02 compara snapshots para generar “Permanece / Salió del catálogo”. Una salida inferida no confirma adopción real, no crea filas en `adopcion` y no debe presentarse como KPI real.
3. **Fecha de captura y calendario:** HU01 valida la fecha del nombre `captura_AAAA-MM-DD.csv` o `captura_demo_AAAA-MM-DD.csv`, deriva la semana ISO y la separa del instante real de importación (`fecha_inicio`/`fecha_fin`).
4. **Calidad de CSV:** se validan encabezados exactos, codificación UTF-8, tamaño, dominios, tipos y SKU duplicados. Los perfiles inválidos se rechazan con un resumen; no se generan valores para completar campos obligatorios.
5. **Vinculación snapshot-dataset:** cada snapshot tiene como máximo un `id_dataset` en esta estructura, que además puede ser nulo. Si HU02 conserva capturas fuente y genera distintas versiones de dataset a partir de ellas, el modelo actual no representa bien una relación muchos-a-muchos. Para una base objetivo considerar una tabla de asociación `dataset_snapshot` o registrar el rango/manifiesto inmutable de snapshots usado por cada dataset.
6. **Seguimiento de alertas:** la tabla guarda fecha, riesgo, mensaje y estado, pero no registra quién atendió la alerta, cuándo ni una nota de resolución. El flujo de HU07 quedaría limitado a cambiar `estado` salvo que se revise el diccionario.
7. **Control de unicidad y dominios:** el diccionario no enumera dominios para estado, sexo, rol, formato y prioridad. La aplicación debe validar esos valores; los `CHECK` añadidos se limitan a rangos numéricos, fechas, estado/origen de las ejecuciones y completitud de snapshots nuevos.
8. **Identidad/idempotencia:** `UNIQUE (sku)` identifica una mascota entre ejecuciones y `UNIQUE (id_ejecucion, id_mascota)` impide duplicarla dentro de una captura. Los CSV deben conservar el SKU para el mismo animal y no reutilizarlo para otro. Cada nombre de archivo se consume una vez. La migración CSV crea el índice único; si hay SKU duplicados existentes, hay que resolverlos antes.
9. **Ejecuciones de recolección:** HU01 puede registrar tipo, inicio/fin, semana, conteos, estado, error y usuario iniciador. “Vigente” se deriva de la última ejecución completada, no se almacena como estado.
10. **Importación CSV:** el Analista selecciona cada archivo y lo envía manualmente. Un archivo exitoso o parcial no se puede repetir con el mismo nombre; uno fallido se puede corregir y reintentar.
11. **Artefactos y parámetros ML:** `modelo_predictivo` registra algoritmo, versión, métricas y fecha, pero no ubicación del archivo entrenado, parámetros, semilla, partición ni cuál modelo está activo.
12. **Datos personales:** `adoptante` contiene nombre, email y teléfono. El acceso debe limitarse y estos datos no deben incluirse como variables del modelo.

El archivo `schema.sql` crea el modelo físico documentado y las extensiones de HU01 para una instalación nueva del esquema anterior. No incluye datos semilla ni capturas CSV.

## Esquema v2 para HU02 y el prototipo

La base nueva `wuf_predict_v2` parte del diccionario original y acomoda las extensiones necesarias para cumplir RF03 y la vista del prototipo. El SQL completo está en [`../backend/schema_wuf_predict_v2.sql`](../backend/schema_wuf_predict_v2.sql). La base `wuf_predict` y su `schema.sql` se conservan sin cambios.

Cambios del diseño v2:

- `ejecucion_recoleccion.fecha_captura` identifica la fecha representada por el CSV; `fecha_inicio` y `fecha_fin` registran cuándo se procesó. `semana` debe coincidir con la semana ISO de `fecha_captura`. La misma fecha/semana se copia al snapshot y el importer valida el nombre del archivo antes de crear la ejecución.
- `snapshot_catalogo.etiqueta_adoptado` se conserva nullable por trazabilidad con el diccionario original, pero no se exige en el CSV ni es la etiqueta objetivo de HU02. HU02 deriva `permanece`, `salio_catalogo` o `indeterminada` a partir de los estados de snapshots sucesivos.
- `snapshot_catalogo.id_dataset` del esquema anterior se sustituye en v2 por `dataset_snapshot`, que hace explícito que varias versiones de dataset pueden reutilizar snapshots y que cada dataset puede agrupar muchas observaciones.
- `dataset_ejecucion` registra las ejecuciones fuente de cada dataset, incluso capturas completas donde una mascota está ausente.
- `dataset_detalle` mantiene una fila por mascota y dataset, vincula snapshots de referencia/resultado y guarda la etiqueta derivada. La clase `salio_catalogo` puede tener snapshot final con estado `no_disponible`, como muestra el prototipo, o no tener snapshot si la mascota falta en una captura completa; en ambos casos se registra la ejecución de resultado. Si no hay evidencia suficiente, la clase es `indeterminada`.
- `dataset_historico` registra rango temporal, versión de regla, procedencia y hash opcional del CSV generado. Los datasets derivados del catálogo se marcan `derivada_catalogo`; esto no significa adopción verificada.

### Regla funcional propuesta a partir del avance original

Una captura CSV debe representar un catálogo completo y una ejecución completada. La regla alineada al prototipo asigna `permanece` si el estado final es `disponible`; asigna `salio_catalogo` si el estado final es `no_disponible` o si el perfil falta en una captura completa posterior. RF03 interpreta la salida como proxy de “adoptada”, pero no se confirma una adopción real. `sin_publicar`, capturas parciales, periodo sin captura posterior o evidencia incompleta producen `indeterminada`. La versión de la regla debe persistirse con el dataset.

La UI del prototipo muestra semanas 6, 7 y 8 como contenido ilustrativo. En los CSV demo fechados 28-sep, 05-oct y 12-oct de 2026, el calendario ISO corresponde a semanas 40, 41 y 42. Se conservará la vista semanal, pero los datos funcionales mostrarán su semana calendario ISO, no copiarán los números estáticos del prototipo.

### Crear `wuf_predict_v2` en pgAdmin

1. En pgAdmin, conéctate al mismo servidor PostgreSQL 16 que usa el proyecto.
2. En **Databases**, crea la base `wuf_predict_v2` con propietario igual al usuario configurado para la aplicación (o al propietario local usado en `wuf_predict`). No borres `wuf_predict`.
3. Selecciona `wuf_predict_v2`, abre **Query Tool**, carga [`../backend/schema_wuf_predict_v2.sql`](../backend/schema_wuf_predict_v2.sql) y ejecútalo una sola vez.
4. Comprueba que se crearon las tablas y restricciones sin error. El script usa transacción y no contiene `DROP DATABASE` ni elimina otra base.
5. Si ejecutaste el primer SQL v2 antes de esta actualización, aplica una sola vez [`../backend/upgrade_wuf_predict_v2_dataset.sql`](../backend/upgrade_wuf_predict_v2_dataset.sql) en `wuf_predict_v2`. Esta agrega el registro de ejecuciones fuente y permite que “Salió” tenga snapshot final `no_disponible` conforme al prototipo.
6. El backend HU01 ahora acepta ambos esquemas, calcula semana ISO desde el nombre del archivo, no persiste la etiqueta sintética y valida la relación mascota/SKU/snapshot/ejecución antes de confirmar. Cambia `DATABASE_URL` local para apuntar a `wuf_predict_v2` y reinicia la API solo cuando la base y el usuario estén preparados. No publiques el `.env`.

La aplicación del SQL y de la migración se ejecuta por separado en pgAdmin; este trabajo no modificó tu PostgreSQL ni sustituye un respaldo de `wuf_predict`.

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
