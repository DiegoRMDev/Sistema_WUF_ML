# HU01 — Recolección desde CSV

> Esta guía contiene antecedentes de la evolución del esquema. La configuración vigente usa `wuf_predict_v6` y los archivos de demostración de `data/capturas/escenario_hu02_variable_v4/`; para iniciar o reiniciar el entorno sigue [`11-inicio-local.md`](11-inicio-local.md). No apliques las migraciones históricas descritas aquí a la base actual.

## Componentes

HU01 conserva las tres capas del proyecto:

- **Presentación:** `frontend/public/` conserva login y pantalla de Recolección conectados a la API; `prototipo/` queda como referencia.
- **Aplicación/API:** `backend/app/api/v1/` protege las rutas para Analista y `backend/app/services/collection_service.py` coordina cada ejecución.
- **Datos/infraestructura:** `CsvCatalogSource` valida el CSV que el Analista selecciona y envía; `CollectionRepository` actualiza `mascota` por SKU y guarda los atributos históricos en PostgreSQL 16.

No se consulta WUF ni se usa `mascota` como origen. `data/capturas/` sirve para organizar los archivos; el backend no la escanea. El frontend permite elegir y enviar el archivo a la API.

## Estado verificado

El usuario confirmó tres importaciones completadas desde la interfaz, cada una con 180 perfiles guardados y ninguno rechazado. El historial mostró las semanas ISO 40, 41 y 42 (28/09/26, 05/10/26 y 12/10/26), con 108 disponibles, 72 no disponibles y 0 sin publicar en cada captura. Esto confirma el recorrido feliz de selección, envío y consulta del historial. Las pruebas unitarias cubren perfiles válidos, campos inválidos, SKU duplicados, CSV sin perfiles válidos y nombre ya importado. La fuente continúa siendo una simulación CSV, sin extracción real ni programación semanal. El reintento de una captura fallida y el acceso denegado a otros roles aún requieren confirmación manual.

## Cómo se procesan varias capturas

1. El Analista selecciona explícitamente un archivo `.csv` desde el botón de importación.
2. El navegador lo envía como `multipart/form-data` a la API; no envía rutas locales.
3. El backend valida extensión, tamaño, UTF-8, encabezados, tipos, longitudes, dominios y SKU duplicados.
4. Registra `fuente_datos='csv_simulada'` y el nombre en `referencia_fuente`. Un CSV procesado correctamente no se puede importar de nuevo con el mismo nombre; uno fallido se puede corregir y reintentar.
5. Reconcilia cada fila con `mascota` por `sku`: actualiza la fila vigente si existe o crea la mascota si es nueva.
6. Inserta un snapshot por mascota y ejecución, con atributos, estado y etiquetas de condición. La etiqueta sintética heredada del CSV se ignora y las columnas `etiqueta_adoptado`/`origen_etiqueta` quedan NULL.

Mantén el SKU para identificar el mismo animal en todos los archivos. Cada CSV debe representar una captura completa y llevar una fecha válida en el nombre: `captura_AAAA-MM-DD.csv` o `captura_demo_AAAA-MM-DD.csv`. El backend deriva la semana ISO de esa fecha y registra aparte la hora real de importación. El Analista elige cada archivo; no hay selección automática por carpeta ni orden alfabético.

## Formato de los archivos

La carpeta predeterminada es `data/capturas/`; su README documenta encabezados y reglas. Cada nombre debe incluir fecha ISO, por ejemplo `captura_2026-10-01.csv`. Los CSV demo están en Git; no subas archivos con datos personales reales.

`etiqueta_adoptado` ya no es obligatorio. Si se recibe en un CSV antiguo, el backend lo valida por compatibilidad pero no lo persiste ni lo usa para HU02. Los snapshots conservan `etiqueta_adoptado=NULL` y `origen_etiqueta=NULL`.

**Etiqueta según el prototipo/RF03:** el estado final `disponible` produce “Permanece”; `no_disponible` produce “Salió del catálogo” como proxy de RF03. Una ausencia en una captura completa también puede representar salida; `sin_publicar` y capturas parciales quedan indeterminadas. Ninguna de estas etiquetas crea filas en `adopcion` ni confirma adopción real.

## Contrato HTTP

La API usa prefijo `/api/v1`. Login no requiere token; las demás rutas HU01 requieren Bearer JWT y rol Analista. El rol se vuelve a leer desde `usuario` en cada solicitud.

| Método y ruta | Propósito |
|---|---|
| `POST /auth/login` | Devuelve JWT de vida limitada; intentos por IP/minuto limitados |
| `GET /auth/me` | Devuelve usuario y rol vigentes |
| `POST /collection-runs` | Recibe el campo `file` como `multipart/form-data` y persiste conteos/resultado |
| `GET /collection-runs?limit=20&offset=0` | Historial paginado, incluye origen y referencia CSV |
| `GET /collection-runs/overview` | Información de la última captura e indica que la siguiente importación es manual |
| `GET /healthz` | Disponibilidad básica de API; no revela configuración |

Estados de ejecución: `en_proceso`, `completada`, `parcial` y `fallida`. Los errores de formato se resumen sin exponer rutas locales ni detalles internos.

## Base `wuf_predict_v2`

El backend ahora reconoce el esquema HU01 anterior y el esquema v2. Si ya ejecutaste el esquema v2 previo a esta actualización, aplica una sola vez [`../backend/upgrade_wuf_predict_v2_dataset.sql`](../backend/upgrade_wuf_predict_v2_dataset.sql) antes de construir datasets; no lo ejecutes sobre `wuf_predict`. La guía del esquema está en [`03-modelo-datos.md`](03-modelo-datos.md). La aplicación lee `DATABASE_URL` desde `backend/.env`; cambia solo el nombre de la base a `wuf_predict_v2` cuando decidas usarla y vuelve a crear el usuario de aplicación en esa base vacía.

## Migración de base existente

En base nueva, ejecutar únicamente `backend/schema.sql`. En la base existente que ya tiene las migraciones HU01 previas:

1. Crear un respaldo en pgAdmin.
2. Aplicar una sola vez `backend/upgrade_hu01_csv.sql` desde pgAdmin Query Tool o `backend/` con:

   ```powershell
   psql -h localhost -U postgres -d wuf_predict -v ON_ERROR_STOP=1 -f .\upgrade_hu01_csv.sql
   ```

La migración elimina únicamente la ejecución `id_ejecucion=1` si todavía es fallida, tiene fuente `wuf`, registra 189 perfiles y no tiene snapshots. Conserva otras ejecuciones sin snapshots. Agrega el archivo de origen y procedencia de etiqueta, marca procedencia desconocida en datasets ya existentes, permite `csv_simulada` como fuente y la fija como predeterminada. También crea una restricción única para SKU. Antes de aplicarla, comprueba que no haya duplicados:

Para confirmar el borrado condicionado antes de ejecutar la migración, revisa la fila y verifica que no tenga snapshots:

```sql
SELECT id_ejecucion, estado, fuente_datos, perfiles_total
FROM ejecucion_recoleccion
WHERE id_ejecucion = 1;

SELECT COUNT(*) AS snapshots_asociados
FROM snapshot_catalogo
WHERE id_ejecucion = 1;
```

La migración solo elimina la fila si coincide con los valores descritos y `snapshots_asociados` es `0`. Si no coincide, se conserva.

```sql
SELECT sku, COUNT(*)
FROM mascota
GROUP BY sku
HAVING COUNT(*) > 1;
```

Si la consulta devuelve filas, corrige las identidades duplicadas antes de la migración. Las etiquetas antiguas con valor reciben procedencia `desconocida`, pues no hay forma fiable de reconstruir su origen. No vuelvas a ejecutar `schema.sql` en una base existente.

## Configuración y operación

En `backend/.env`, configura:

```dotenv
CATALOG_CSV_MAX_BYTES=20000000
```

La API recibe el archivo seleccionado en cada solicitud. Si supera el tamaño máximo, se rechaza antes de procesarlo.

## Reglas de integridad y seguridad

- El Analista selecciona el archivo; su nombre se guarda para auditoría y nunca se interpreta como una ruta del servidor.
- Los archivos se limitan por tamaño y deben usar UTF-8. Los encabezados deben coincidir exactamente con el contrato.
- Se rechazan filas incompletas o con valores desconocidos; no se inventan atributos. SKU duplicados del mismo CSV quedan rechazados.
- SKU identifica mascotas entre capturas. El backend valida tras persistir que `snapshot.sku` coincide con `mascota.sku`, y que la fecha/semana del snapshot corresponde a la ejecución.
- `etiqueta_adoptado` no es obligatoria: si un CSV legado la incluye, el backend la valida y descarta; los snapshots nuevos guardan ambos campos de etiqueta heredada como NULL. HU02 derivará su etiqueta comparando snapshots.
- Se usan consultas SQL parametrizadas, autenticación JWT, autorización por rol, CORS por allowlist y contraseñas Argon2.
- El nombre del CSV queda en la auditoría de ejecución, pero no se devuelve una ruta local del servidor.

## Límites conocidos

La simulación depende de la calidad y completitud de los CSV. Los tres archivos base contienen 180 perfiles por semana y estados inspirados en el prototipo; las semanas ISO son 40, 41 y 42 de 2026. En ese conjunto cada SKU conserva su estado. Para probar transiciones HU02 se creó una variante separada en `data/capturas/escenario_hu02_v3/`, que se importa en una base limpia aparte. `no_disponible` se usa como proxy para la etiqueta “Salió del catálogo”, no como adopción verificada. Para entrenamiento se debe particionar por SKU o por tiempo para evitar fuga entre snapshots de la misma mascota.

## Cierre de HU01 y seguimiento

HU01 se considera completada dentro del alcance acordado: el usuario confirmó tres importaciones válidas de 180 perfiles cada una, consultó el historial y probó un CSV inválido, cuya validación funcionó. La extracción automática de WUF y la programación semanal no forman parte de este alcance.

La verificación manual de acceso denegado para un usuario de otro rol se deja como seguimiento transversal para HU08, donde se revisará la autorización por roles en el sistema. La auditoría directa de filas en PostgreSQL (esperadas en la base limpia: 3 ejecuciones, 180 mascotas y 540 snapshots) es opcional; la interfaz confirmó las tres ejecuciones completadas.
