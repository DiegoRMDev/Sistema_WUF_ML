# Guía para iniciar WUF Predict en Windows

Esta guía permite que otra persona prepare el entorno local y ejecute el backend y el frontend de WUF Predict. Está escrita para PowerShell y PostgreSQL 16.

## Requisitos

- Windows y PowerShell.
- Python 3.12 o 3.13. Comprueba las versiones disponibles con `py --list`.
- PostgreSQL 16 instalado y en ejecución.
- Para la configuración nueva: una base `wuf_predict_v2` y un usuario PostgreSQL con permisos sobre ella. La base antigua `wuf_predict` puede conservarse como respaldo.
- Git, si se descargó el proyecto desde GitHub.

> Los comandos no requieren instalar herramientas pagadas. Las dependencias de Python se declaran en `backend/pyproject.toml`.

## A. Preparar la base de datos

### Base ya creada y migrada para HU01 CSV

Si la base ya tiene el esquema inicial y se aplicaron las migraciones `upgrade_hu01.sql`, `upgrade_hu01_etiqueta.sql`, `upgrade_hu01_simulacion.sql` y `upgrade_hu01_csv.sql`, no vuelvas a ejecutarlas. Continúa en la sección B. Aplica solo las migraciones que aún falten en la base, siguiendo el orden de esta guía y conservando un respaldo.

### Base existente pendiente de migraciones HU01

Si la base ya tiene el esquema inicial y se aplicó `upgrade_hu01.sql`, hacer una copia de seguridad y aplicar **una sola vez** `backend/upgrade_hu01_etiqueta.sql` a `wuf_predict`. Se puede ejecutar desde pgAdmin Query Tool o desde PowerShell, estando en `backend/`:

```powershell
psql -h localhost -U postgres -d wuf_predict -v ON_ERROR_STOP=1 -f .\upgrade_hu01_etiqueta.sql
```

Antes de la última migración, comprueba que no existan SKU repetidos (el índice único finaliza la migración si hay duplicados):

```sql
SELECT sku, COUNT(*) FROM mascota GROUP BY sku HAVING COUNT(*) > 1;
```

La migración permite que `snapshot_catalogo.etiqueta_adoptado` quede pendiente (`NULL`) hasta que se defina la etiqueta correspondiente. No elimina ni cambia los valores que ya existan. Después, aplica **una sola vez** la migración que registra la fuente de cada ejecución:

```powershell
psql -h localhost -U postgres -d wuf_predict -v ON_ERROR_STOP=1 -f .\upgrade_hu01_simulacion.sql
```

Las ejecuciones anteriores conservan su fuente histórica. Después aplica la migración CSV **una sola vez**:

```powershell
psql -h localhost -U postgres -d wuf_predict -v ON_ERROR_STOP=1 -f .\upgrade_hu01_csv.sql
```

Esta migración elimina ejecuciones sin snapshots (por ejemplo, intentos fallidos vacíos), conserva ejecuciones con capturas y agrega el nombre del archivo y la procedencia de etiquetas. No ejecutes `schema.sql` sobre una base existente.

### Base nueva v2

Crea `wuf_predict_v2` desde pgAdmin, selecciona UTF8 y ejecuta una sola vez `backend/schema_wuf_predict_v2.sql` en su Query Tool. El esquema está pensado para una base vacía; no ejecutes las migraciones HU01 antiguas ni borres `wuf_predict`.

Si ya ejecutaste una primera versión del esquema v2 antes de este ajuste, ejecuta también una sola vez `backend/upgrade_wuf_predict_v2_dataset.sql` en `wuf_predict_v2`. No la ejecutes sobre la base antigua.

En la siguiente sección de configuración, conserva host, puerto, usuario y contraseña de tu conexión y cambia solo el nombre de la base en `DATABASE_URL` a `wuf_predict_v2`. Crea nuevamente el usuario Analista en esa base vacía.

### Base antigua `wuf_predict`

Si deseas seguir usando la base antigua, continúa con las subsecciones de migraciones HU01 existentes y apunta `DATABASE_URL` a `wuf_predict`. El backend reconoce ambos esquemas. No vuelvas a ejecutar `schema.sql` sobre una base existente.

## B. Crear el entorno e instalar dependencias

Abre PowerShell y entra a la carpeta `backend` del proyecto:

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\backend
```

Elige el comando que corresponda a la versión de Python instalada:

```powershell
py -3.13 -m venv .venv
```

O bien:

```powershell
py -3.12 -m venv .venv
```

Activa el entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación por su política de scripts, permite scripts solo en la ventana actual y vuelve a activarlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Instala las dependencias declaradas por el proyecto:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip check
```

El último comando comprueba que no haya dependencias incompatibles. Al terminar, el prompt de PowerShell debe mostrar `(.venv)`.

## C. Crear la configuración local `.env`

Desde `backend/`, copia el archivo de ejemplo:

```powershell
Copy-Item .env.example .env
```

Edita `backend/.env` y sustituye, como mínimo, estos valores:

```dotenv
DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5432/wuf_predict_v2
JWT_SECRET=REEMPLAZAR_POR_UN_SECRETO_ALEATORIO_DE_AL_MENOS_32_CARACTERES
```

Usa tu usuario y contraseña reales de PostgreSQL. Si la contraseña tiene caracteres reservados de URL como `@`, `:`, `/` o `#`, codifícalos para el formato URL antes de ponerla en `DATABASE_URL`.

Genera el secreto JWT desde `backend/`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia el resultado como valor de `JWT_SECRET` en `.env`. No compartas ese secreto ni subas `.env` al repositorio. El `.gitignore` excluye `.env`.

Para el primer inicio local, conserva el resto de valores del ejemplo. HU01 procesa el archivo CSV que el Analista elige y envía desde la interfaz; la API no escanea `data/capturas/`. Cada archivo debe mantener SKU estables y usar un nombre `captura_AAAA-MM-DD.csv` o `captura_demo_AAAA-MM-DD.csv`; el backend valida la fecha y deriva su semana ISO. `etiqueta_adoptado` no es necesaria; si aparece en un CSV heredado, se descarta y no alimenta HU02. Configura `CATALOG_CSV_MAX_BYTES` para el límite de tamaño.

## D. Crear el usuario de la aplicación

Con el entorno virtual activo y desde `backend/`, ejecuta:

```powershell
python -m scripts.create_user
```

Ingresa nombre, correo, rol y contraseña. Para ejecutar la HU01, crea el usuario con rol `analista`. El programa pide una contraseña de al menos 12 caracteres y la guarda como hash Argon2.

Los valores admitidos por el script son `analista`, `marketing` y `ayuda`. Solo el rol Analista puede ejecutar y consultar la recolección HU01.

## E. Crear `config.js` del frontend

Abre otra ventana de PowerShell y copia el archivo de ejemplo:

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\frontend\public
Copy-Item config.js.example config.js
```

El archivo ya apunta a la API local esperada:

```js
window.WUF_CONFIG = {
  apiBaseUrl: "http://127.0.0.1:8000/api/v1",
};
```

Si cambias el host o puerto de la API, actualiza aquí `apiBaseUrl` y también `CORS_ORIGINS` en `backend/.env` con el origen exacto del frontend. `config.js` está excluido de Git.

## F. Arrancar el programa

Se necesitan dos ventanas de PowerShell y ambas deben permanecer abiertas.

### Ventana 1: backend

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Comprueba la disponibilidad abriendo <http://127.0.0.1:8000/healthz>. La respuesta esperada es:

```json
{"status":"ok"}
```

La documentación interactiva de la API está en <http://127.0.0.1:8000/docs>.

### Ventana 2: frontend

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\frontend
python -m http.server 5500 --bind 127.0.0.1 --directory public
```

Abre <http://127.0.0.1:5500> e inicia sesión con el correo y la contraseña del usuario Analista.

No abras `index.html` directamente como archivo; el servidor local permite que el navegador se comunique correctamente con la API.

## G. Importar una captura CSV

Desde la aplicación, entra a Recolección, selecciona un archivo CSV con **Elegir archivo CSV** y luego pulsa **Importar archivo seleccionado**. El primer botón solo selecciona el archivo en el navegador; el segundo lo envía al backend para validarlo y guardarlo. Revisa el estado, el número de perfiles válidos/rechazados y el historial.

Una captura parcial indica que algunas filas CSV no cumplen encabezados, tipos, dominios o restricciones del esquema. Revisa el resumen de incidencias, corrige los datos y guarda el archivo con un nombre nuevo. La importación es manual; no hay una programación semanal activa.

Para apagar los servidores, detén cada uno con `Ctrl+C` en su ventana de PowerShell.

## Para los siguientes inicios

No hace falta recrear `.venv`, reinstalar dependencias, volver a ejecutar migraciones, ni recrear `config.js` o el usuario. Abre dos ventanas, activa `.venv` en la del backend, inicia ambos servidores siguiendo la sección F e inicia sesión.

## Solución de problemas frecuentes

- **`py -3.13` o `py -3.12` no se encuentra:** instala una versión compatible de Python y vuelve a comprobarla con `py --list`.
- **Error al activar `.venv`:** ejecuta el `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` indicado en la sección B en esa ventana de PowerShell.
- **Error de conexión a PostgreSQL al arrancar la API:** confirma que PostgreSQL esté activo, que `wuf_predict` exista y que `DATABASE_URL` tenga credenciales correctas.
- **La API falla indicando que falta la migración de HU01:** revisa que `upgrade_hu01.sql` y `upgrade_hu01_etiqueta.sql` se hayan aplicado a la base correcta. No repitas una migración ya aplicada sin revisar antes su contenido y el estado del esquema.
- **El login no funciona:** verifica que creaste el usuario en la misma base indicada por `DATABASE_URL`, que el rol sea `analista` y que `config.js` apunte al backend correcto.
- **Error CORS en el navegador:** revisa que `CORS_ORIGINS` enumere el origen exacto abierto en el navegador, incluido protocolo, host y puerto. No agregues rutas como `/api/v1` a ese valor.
- **La API abre, pero la importación falla o queda parcial:** revisa el mensaje de la aplicación y los logs del backend. Comprueba que el archivo respete el contrato descrito en `data/capturas/README.md`; la aplicación no consulta WUF.

Para detalles de HU01, sus rutas API, migraciones y límites de la importación simulada, consulta [`10-hu01-recoleccion.md`](10-hu01-recoleccion.md).
