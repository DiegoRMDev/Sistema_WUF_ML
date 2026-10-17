# HU01 — Recolección desde CSV

## Componentes

HU01 conserva las tres capas del proyecto:

- **Presentación:** `frontend/public/` conserva login y pantalla de Recolección conectados a la API; `prototipo/` queda como referencia.
- **Aplicación/API:** `backend/app/api/v1/` protege las rutas para Analista y `backend/app/services/collection_service.py` coordina cada ejecución.
- **Datos/infraestructura:** `CsvCatalogSource` valida el CSV que el Analista selecciona y envía; `CollectionRepository` actualiza `mascota` por SKU y guarda los atributos históricos en PostgreSQL 16.

No se consulta WUF ni se usa `mascota` como origen. `data/capturas/` sirve para organizar los archivos; el backend no la escanea. El frontend permite elegir y enviar el archivo a la API.

## Estado verificado

El usuario confirmó dos importaciones completadas desde la interfaz, cada una con 60 perfiles guardados y ninguno rechazado. El historial reportó 49 disponibles, 4 no disponibles y 7 sin publicar en una ejecución; en la otra, 43 disponibles, 13 no disponibles y 4 sin publicar. Esta revisión añadió pruebas unitarias para conteo de perfiles válidos, conteo correcto de una fila con varios errores y duplicados de SKU dentro del archivo. La fuente continúa siendo una simulación CSV, sin extracción real ni programación semanal. El reintento desde UI y el acceso negado a otros roles siguen requiriendo confirmación manual.

## Cómo se procesan varias capturas

1. El Analista selecciona explícitamente un archivo `.csv` desde el botón de importación.
2. El navegador lo envía como `multipart/form-data` a la API; no envía rutas locales.
3. El backend valida extensión, tamaño, UTF-8, encabezados, tipos, longitudes, dominios y SKU duplicados.
4. Registra `fuente_datos='csv_simulada'` y el nombre en `referencia_fuente`. Un CSV procesado correctamente no se puede importar de nuevo con el mismo nombre; uno fallido se puede corregir y reintentar.
5. Reconcilia cada fila con `mascota` por `sku`: actualiza la fila vigente si existe o crea la mascota si es nueva.
6. Inserta un snapshot por mascota y ejecución. El snapshot guarda la etiqueta sintética explícita y `origen_etiqueta='sintetica'`.

Mantén el SKU para identificar el mismo animal en todos los archivos. Cada CSV debe ser una captura completa fechada por su nombre. El Analista elige cada archivo a importar; no existe selección automática por carpeta ni orden alfabético.

## Formato de los archivos

La carpeta predeterminada es `data/capturas/`; ahí se encuentra su README con la lista de encabezados y reglas de formato. Los nombres sugeridos son `captura_2026-10-01.csv`, `captura_2026-10-08.csv`, etc. Los CSV locales se excluyen de Git.

`etiqueta_adoptado` es obligatoria y acepta `true` o `false`. El sistema la persiste solo en `snapshot_catalogo`, junto a la procedencia sintética. **No** crea filas en `adopcion`, no confirma hechos reales y no se debe usar como KPI real. HU02 debe copiar la procedencia al CSV de dataset; HU03 debe marcar el entrenamiento sintético como experimental y bloquear su activación operativa.

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
- SKU identifica mascotas entre capturas; `UNIQUE (id_ejecucion, id_mascota)` evita repetición dentro de una ejecución.
- La etiqueta sintética se guarda con su procedencia y no se inserta en `adopcion`.
- Se usan consultas SQL parametrizadas, autenticación JWT, autorización por rol, CORS por allowlist y contraseñas Argon2.
- El nombre del CSV queda en la auditoría de ejecución, pero no se devuelve una ruta local del servidor.

## Límites conocidos

La simulación depende de la calidad de los CSV preparados. Las etiquetas sintéticas sirven para verificar construcción de dataset y entrenamiento, no para afirmar precisión de adopciones reales. Si solo se cambia la etiqueta sin crear suficientes ejemplos independientes, las métricas no son evidencia de desempeño. Para entrenamiento se debe agrupar la partición por mascota y separar cualquier dataset sintético de modelos operativos.
