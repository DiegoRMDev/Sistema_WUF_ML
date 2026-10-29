# Guía para iniciar WUF Predict en Windows

Esta guía explica cómo configurar y ejecutar la versión actual del proyecto en Windows con PowerShell, PostgreSQL 16, la base nueva `wuf_predict_v7` e importaciones manuales de CSV.

## Requisitos

- Windows y PowerShell.
- Python 3.12 o 3.13. Comprueba la instalación con `py --list`.
- PostgreSQL 16 y pgAdmin.
- Git, si descargaste el proyecto desde GitHub.

Las dependencias gratuitas y abiertas del backend están declaradas en `backend/pyproject.toml` e incluyen FastAPI, scikit-learn, pandas, joblib, openpyxl y ReportLab.

## 1. Preparar PostgreSQL 16

La base anterior `wuf_predict_v6` se conserva como respaldo de trabajo. Para la versión con HU07 crea **`wuf_predict_v7`** y ejecuta [`../backend/schema_wuf_predict_v5.sql`](../backend/schema_wuf_predict_v5.sql), que instala el esquema limpio integrado para HU01–HU07.

1. Conserva `wuf_predict_v6`; crea una base nueva `wuf_predict_v7` con codificación UTF8.
2. Abre Query Tool conectado específicamente a la base nueva.
3. Ejecuta `backend/schema_wuf_predict_v5.sql` una sola vez.
4. No ejecutes el instalador sobre `wuf_predict_v6` ni apliques scripts `upgrade_*.sql` a la base nueva.

La configuración `DATABASE_URL` de `backend/.env` debe apuntar a `wuf_predict_v7`. Los CSV actuales se vuelven a importar manualmente en esa base nueva.

## 2. Crear el entorno e instalar dependencias

Abre PowerShell y entra a la carpeta del backend:

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\backend
```

Crea el entorno virtual con Python 3.13 o 3.12:

```powershell
py -3.13 -m venv .venv
```

Si usas Python 3.12, ejecuta en su lugar:

```powershell
py -3.12 -m venv .venv
```

Activa el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación, habilita scripts solo en esa ventana y vuelve a activarlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Instala las dependencias:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip check
```

El último comando revisa incompatibilidades entre dependencias. El prompt debe mostrar `(.venv)`.

## 3. Configurar `backend/.env`

Desde `backend/`, crea la configuración local:

```powershell
Copy-Item .env.example .env
```

Abre `backend/.env` y confirma estos valores. Reemplaza el usuario y la contraseña por las credenciales reales de PostgreSQL:

```dotenv
DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5432/wuf_predict_v7
JWT_SECRET=REEMPLAZAR_POR_UN_SECRETO_ALEATORIO_DE_AL_MENOS_32_CARACTERES
```

Genera el secreto JWT desde `backend/`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia el resultado como `JWT_SECRET`. Si la contraseña de PostgreSQL contiene caracteres reservados para URL —por ejemplo `@`, `:`, `/` o `#`— codifícalos antes de ponerla en `DATABASE_URL`. No compartas `.env` ni lo subas a Git.

Para el primer inicio puedes conservar los demás valores de `.env.example`. Algunos parámetros importantes son:

- `CORS_ORIGINS`: orígenes locales permitidos para el frontend.
- `MODEL_ARTIFACT_DIR`: carpeta privada donde se guardan los modelos entrenados.
- `MODEL_PRIORITY_HIGH_MAX` y `MODEL_PRIORITY_MEDIUM_MAX`: bandas de prioridad de HU03.
- `CONSISTENCY_*`: parámetros de entrenamiento y regla demo de HU04.
- `CATALOG_CSV_MAX_BYTES`: tamaño máximo permitido para un CSV.

Los valores de demostración están documentados en [`../backend/.env.example`](../backend/.env.example). No guardes archivos de modelo dentro de `frontend/public/`.

## 4. Crear usuarios de la aplicación

Con el entorno virtual activo, ejecuta desde `backend/`:

```powershell
python -m scripts.create_user
```

Ingresa nombre, correo, rol y contraseña. Crea un usuario **Analista** para importar CSV y operar HU01–HU04. Para probar el reporte HU05, puedes crear también un usuario **Marketing**. Los roles disponibles son `analista`, `marketing` y `ayuda`; el programa guarda las contraseñas como hash Argon2.

Los usuarios de la aplicación son distintos del usuario/contraseña de PostgreSQL que se configuran en `DATABASE_URL`.

## 5. Configurar el frontend

Abre otra ventana de PowerShell y copia el archivo de configuración de ejemplo:

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\frontend\public
Copy-Item config.js.example config.js
```

El archivo debe apuntar a la API local:

```js
window.WUF_CONFIG = {
  apiBaseUrl: "http://127.0.0.1:8000/api/v1",
};
```

`config.js` está excluido de Git. Si cambias el host o puerto, actualiza también `CORS_ORIGINS` en `backend/.env` con el origen exacto del frontend.

## 6. Iniciar el programa

Deja abiertas dos ventanas de PowerShell.

### Ventana 1: backend

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Abre <http://127.0.0.1:8000/healthz>. Debe responder:

```json
{"status":"ok"}
```

La documentación interactiva de la API está en <http://127.0.0.1:8000/docs>.

### Ventana 2: frontend

```powershell
cd C:\Users\DIEGO\Desktop\WUF_PREDICT\frontend
python -m http.server 5500 --bind 127.0.0.1 --directory public
```

Abre <http://127.0.0.1:5500> e inicia sesión con el usuario de la aplicación.

No abras `index.html` directamente como archivo: el servidor local permite la comunicación con la API.

## 7. Flujo de uso de los módulos

1. En **Recolección**, selecciona un CSV y pulsa **Importar archivo seleccionado**. La importación se inicia manualmente desde la interfaz; el backend no escanea `data/capturas/` ni consulta la página de WUF.
2. Los CSV deben usar nombres como `captura_2026-10-12.csv` o `captura_demo_2026-10-12.csv`. El backend valida la fecha del nombre y deriva la semana ISO. Mantén el mismo SKU para una misma mascota entre capturas.
3. Importa las capturas de HU02 en orden cronológico. Luego genera el dataset histórico.
4. Para HU03, entrena y publica un modelo; después actualiza las predicciones de la última captura completa.
5. Para HU04, entrena y consulta el árbol de decisión. Se necesitan capturas completas suficientes para formar observaciones.
6. En HU05, Analista o Marketing pueden consultar el reporte de la última captura y exportarlo a PDF o Excel. Se genera a demanda; no hay programación automática semanal.

Los CSV de demostración están en `data/capturas/`. Para las pruebas actuales de HU01–HU06 usa los tres archivos de `escenario_hu02_variable_v4`; v3 se conserva para reproducir pruebas anteriores. V4 mantiene el escenario variable 180→165→190, corrige las etiquetas derivadas de atributos y las edades faltantes. Son datos sintéticos y sus etiquetas no representan adopciones ni verificaciones reales.

Si una importación resulta parcial o fallida, revisa las incidencias mostradas en la interfaz, corrige el archivo y vuelve a importarlo con un nombre que represente la fecha de captura correcta.

## 8. Detener y volver a iniciar

Para detener cualquiera de los servidores, pulsa `Ctrl+C` en su ventana de PowerShell.

En los siguientes inicios no recrees la base, el entorno virtual, los usuarios ni `config.js`. Abre dos ventanas, activa `.venv` en la del backend y vuelve a ejecutar los comandos de la sección 6.

## Solución de problemas

- **No se activa `.venv`:** aplica `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` en esa ventana y vuelve a activar el entorno.
- **La API no conecta a PostgreSQL:** confirma que PostgreSQL 16 esté en ejecución, que `wuf_predict_v7` exista y que `DATABASE_URL` tenga las credenciales correctas.
- **La API indica que faltan dependencias:** activa `.venv`, ejecuta `python -m pip install -e .` y reinicia Uvicorn.
- **El login falla:** confirma que el usuario fue creado en `wuf_predict_v7` y que `config.js` apunta a la API local.
- **Error CORS:** el origen abierto en el navegador debe estar listado en `CORS_ORIGINS`, por ejemplo `http://127.0.0.1:5500`; no agregues `/api/v1` a ese valor.
- **La importación CSV falla o es parcial:** revisa el mensaje de incidencias y el contrato de [`../data/capturas/README.md`](../data/capturas/README.md). El sistema usa la importación manual y no consulta WUF.

Para más contexto sobre la recolección manual, consulta [`10-hu01-recoleccion.md`](10-hu01-recoleccion.md); para el reporte semanal, consulta [`16-hu05-reporte-priorizacion.md`](16-hu05-reporte-priorizacion.md).

## Pendiente para el cierre del proyecto: instalación limpia única

Al terminar el desarrollo se consolidará el esquema final en un único archivo SQL de instalación limpia, sin requerir migraciones para una instalación nueva. La base final podría llamarse `wuf_predict_db`; el nombre todavía no está definido y se configurará mediante `DATABASE_URL` en `backend/.env`, no se fijará en el código.

En ese cierre también se debe revisar `backend/app/infrastructure/database.py`: reemplazar las comprobaciones que aceptan esquemas antiguos por una validación del esquema final completo, y actualizar sus errores para que indiquen la ruta del SQL limpio vigente y que se revisen tanto `DATABASE_URL` como la instalación del esquema. El backend solo debe detectar una configuración/esquema incorrecto; no debe ejecutar SQL ni crear o borrar bases automáticamente.

Los scripts `upgrade_*.sql` podrán conservarse como referencia histórica si se desea, pero no deben aparecer como pasos para instalar el proyecto final desde cero. Al completar la consolidación, actualizar esta guía, `backend/.env.example` y las referencias de instalación en `docs/` con el nombre y archivo SQL definitivos.
