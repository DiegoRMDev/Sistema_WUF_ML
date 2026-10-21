# Arquitectura tecnológica y estructura

## Línea base tecnológica

**Definido en el avance:** frontend HTML5/CSS3/JavaScript; backend Python 3.12 y FastAPI como API REST; PostgreSQL 16 con SQLAlchemy; scikit-learn (`RandomForestClassifier`, `DecisionTreeClassifier`), pandas y joblib; APScheduler para tareas futuras; openpyxl y ReportLab para exportaciones; Lucide para iconos. **Implementado actualmente:** HU01 recibe una captura CSV seleccionada manualmente por el Analista; todavía no hay consulta automática a WUF ni programación periódica. El archivo H01 estandarizado con 189 registros es dataset de referencia/desarrollo, no debe asumirse como dataset productivo vivo.

## Arquitectura de tres capas

La separación acordada mantiene las tres capas: **presentación** (`frontend/public/`), **aplicación** (API FastAPI, autorización y servicios de caso de uso) y **datos** (repositorios/infraestructura y PostgreSQL 16). El validador CSV es un adaptador de entrada de la capa de aplicación; no reemplaza ninguna capa. El navegador nunca se conecta directamente a PostgreSQL.

```mermaid
flowchart LR
  U[Analista / Marketing / Área de Ayuda] --> FE[Frontend HTML CSS JS]
  FE -->|HTTP local / HTTPS desplegado| API[FastAPI: API y autorización]
  API --> APP[Servicios de aplicación]
  APP --> DB[(PostgreSQL 16 / SQLAlchemy)]
  APP --> ML[Entrenamiento y predicción scikit-learn]
  ANALYST[Analista selecciona CSV] -->|multipart/form-data| API
  APP --> SRC[Validador CSV]
  APP --> EXP[Exportación PDF / Excel / CSV]
  ML --> ART[Artefactos versionados del modelo]
```

El navegador es cliente sin secretos ni lógica autoritativa. La API valida la sesión, permisos, entrada y estado de negocio. Los servicios de dominio no dependen de HTTP ni de componentes visuales. Los adaptadores aíslan PostgreSQL, CSV locales, filesystem/artefactos y exportadores.

## Componentes backend

- **Identidad y autorización:** autenticación, usuario, rol y comprobación de permiso por endpoint/acción.
- **Catálogo:** cliente de fuente, normalización, captura idempotente y registro de ejecuciones.
- **Dataset:** selección de snapshots, creación de etiqueta, codificación reproducible, exportación y versiones.
- **ML:** entrenamiento/evaluación, registro de métricas, activación explícita del modelo y predicciones reproducibles.
- **Consistencia/alertas:** evaluación del riesgo, explicación, deduplicación, persistencia y atención.
- **Reportes/KPI:** consulta de datos consistentes, reglas versionadas y exportaciones.
- **Configuración/auditoría:** umbrales editables con permiso, bitácora de cambios y eventos operativos.

## API propuesta (nombres de recurso; validar contrato al implementar)

| Área | Rutas sugeridas | Permiso |
|---|---|---|
| Sesión | `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me` | Público solo login; autenticado resto |
| Catálogo | `GET /api/v1/pets`, `GET /api/v1/pets/{id}` | Tres roles |
| Capturas | `POST /api/v1/collection-runs`, `GET /api/v1/collection-runs` | Analista |
| Dataset | `GET /api/v1/datasets/sources`, `POST /api/v1/datasets`, `GET /api/v1/datasets`, `GET /api/v1/datasets/{id}`, `GET /api/v1/datasets/{id}/export` | Analista |
| Modelos | `GET /api/v1/models/options`, `POST /api/v1/models/train`, `GET /api/v1/models`, `POST /api/v1/models/{id}/activate`, `POST /api/v1/models/{id}/refresh-predictions` | Analista |
| Predicciones de catálogo | `GET /api/v1/models/predictions` | Tres roles autenticados |
| Alertas | `GET /api/v1/alerts`, `PATCH /api/v1/alerts/{id}` | Analista/Ayuda según acción |
| Reportes | `POST /api/v1/reports`, `GET /api/v1/reports`, `GET /api/v1/reports/{id}/file` | Analista/Marketing |
| Indicadores | `GET /api/v1/indicators?from=&to=` | Tres roles |
| Configuración | `GET/PATCH /api/v1/settings` | Lectura autenticada; escritura Analista |

Respuestas de error estables, paginación y filtros tipados deben ser comunes. No devolver rutas locales de artefactos ni trazas internas.

## Flujo de HU y transacciones

1. El Analista selecciona un archivo CSV en la interfaz y lo envía al backend como `multipart/form-data`; no se envía una ruta del equipo ni se escanea automáticamente una carpeta.
2. El backend crea `ejecucion_recoleccion` y registra actor, fecha de captura tomada del nombre validado del archivo, fechas de procesamiento, semana ISO, estado, contadores, nombre de archivo y errores resumidos. Aplica límite de bytes y valida encabezados, tipos, dominios, longitudes y SKU duplicados. Una captura parcial se declara parcial y no se presenta como completa.
3. Actualizar `mascota` como estado vigente y guardar una copia de todos los atributos en `snapshot_catalogo`, ligada a ejecución y mascota. Guardar las etiquetas en `snapshot_etiqueta_condicion`; la unicidad por ejecución/mascota hace idempotente el guardado.
4. Construir dataset desde snapshots identificables y política de etiquetas versionada; persistir metadatos y hash/versión del CSV.
5. HU03 prepara los atributos de la captura de referencia, excluye las etiquetas indeterminadas, separa perfiles por SKU y entrena un pipeline reproducible. Registra métricas, parámetros y motivos excluidos; el artefacto se conserva fuera del webroot y se verifica por SHA-256.
6. Un modelo candidato solo puede publicarse si supera el umbral configurable de Accuracy. La publicación es explícita; calcula predicciones para mascotas disponibles de la última captura completa y registra también el `id_ejecucion` fuente. Tras una captura nueva, el Analista puede actualizar predicciones con el modelo vigente.
7. Evaluar consistencia, crear alertas idempotentes; permitir atención y auditoría.
8. Reportes y dashboard se construyen desde datos persistidos y exponen periodo, fecha de cálculo y versión/regla usada.

## Estructura objetivo propuesta

La siguiente estructura es la guía para completar el producto al avanzar por las HU. **Es una propuesta futura, no una descripción de carpetas que deban existir ya.** Se actualizará al cierre del proyecto para reflejar lo que finalmente se implemente.

```text
WUF_PREDICT/
├── docs/                         # Requisitos, arquitectura, manuales y decisiones
├── prototipo/                    # Referencia estática original
├── frontend/                     # Cliente web por historias de usuario
│   ├── src/
│   │   ├── api/                  # Cliente HTTP y contratos de API
│   │   ├── auth/                 # Sesión y control de navegación por rol
│   │   ├── components/           # Componentes compartidos
│   │   ├── pages/                # Vistas por módulo/HU
│   │   └── styles/               # Estilos y tokens visuales
│   └── public/                   # Recursos estáticos y configuración local
├── backend/
│   ├── app/
│   │   ├── api/v1/               # routers y endpoints versionados
│   │   ├── core/                 # configuración tipada y seguridad
│   │   ├── domain/               # reglas y entidades del dominio
│   │   ├── services/             # casos de uso por módulo
│   │   ├── infrastructure/      # PostgreSQL, CSV y almacenamiento
│   │   └── main.py               # aplicación FastAPI y middleware
│   ├── scripts/                  # administración reproducible
│   ├── migrations/               # migraciones versionadas del esquema
│   ├── tests/                    # pruebas unitarias e integración
│   ├── schema.sql                # esquema base para instalación nueva
│   ├── .env.example              # nombres de configuración sin secretos
│   └── pyproject.toml
├── data/
│   └── capturas/                 # CSV de demostración o importación local
├── artifacts/                    # modelos y artefactos versionados/controlados
├── scripts/                      # tareas de soporte del proyecto
├── .env.example                  # configuración general de ejemplo
├── .gitignore
└── README.md                     # inicio rápido y enlaces a documentación
```

### Estructura que existe ahora

Actualmente hay `docs/`, `prototipo/`, `frontend/public/`, `backend/app/` (api, core, domain, services e infrastructure), `backend/scripts/`, `backend/tests/`, SQL de esquemas/migraciones y `.gitignore`. HU02 se organiza en `backend/app/domain/dataset.py`, `backend/app/services/dataset_service.py`, `backend/app/infrastructure/dataset_repository.py` y `backend/app/api/v1/datasets.py`. HU03 usa `model_training.py`, `model_service.py`, `model_repository.py`, `model_artifact_storage.py` y `api/v1/models.py`; el frontend conserva la estructura visual bajo `frontend/public/`. Los artefactos entrenados se guardan en la carpeta privada `artifacts/models/` (ignorada por Git). Los CSV controlados se guardan en `data/capturas/`. `frontend/src/`, `backend/migrations/`, `scripts/` en la raíz y `README.md` raíz siguen siendo estructura propuesta para etapas posteriores. El backend no consulta WUF ni escanea automáticamente la carpeta de capturas.

## Esquema v2/v3 para HU02, HU03 y el prototipo

Para HU02 se preparó [`../backend/schema_wuf_predict_v2.sql`](../backend/schema_wuf_predict_v2.sql), derivado del diccionario físico original. Se puede ejecutar en una base vacía `wuf_predict_v2` o `wuf_predict_v3`; para la prueba aislada se usa v3. Añade fecha de captura separada de la importación y relaciones versionadas entre dataset, ejecuciones y snapshots. HU03 añade persistencia de experimentos y predicciones; para una base v2/v3 existente se aplica [`../backend/upgrade_hu03_ml.sql`](../backend/upgrade_hu03_ml.sql). El SQL completo no migra ni borra bases existentes.

El backend de HU01 valida la fecha desde el nombre del archivo, y el guardado comprueba mascota/SKU/snapshot/ejecución. HU02 requiere el esquema v2 completo, genera la cohorte de mascotas disponibles al inicio y persiste snapshots, ejecuciones fuente, etiquetas y hash. Consulta [`13-hu02-dataset-historico.md`](13-hu02-dataset-historico.md).

## HU01 implementada

- Login con Argon2 y JWT de vida limitada; rol cargado desde PostgreSQL en cada solicitud; captura e historial protegidos para Analista.
- `POST /api/v1/collection-runs`, `GET /api/v1/collection-runs`, `GET /api/v1/collection-runs/overview`; sesión y perfil en `/api/v1/auth/login` y `/api/v1/auth/me`.
- Recolección manual de un archivo CSV elegido por el Analista.
- `CsvCatalogSource` valida el CSV UTF-8 recibido por la API; no lee la carpeta del servidor. `CollectionRepository` reconcilia y actualiza `mascota` por SKU y crea un snapshot completo por ejecución.
- `etiqueta_adoptado` es opcional únicamente para compatibilidad con CSV antiguos: el importador actual lo descarta y guarda NULL. HU02 deriva “Permanece / Salió del catálogo” al comparar snapshots. La etiqueta de salida es un proxy y no crea una fila en `adopcion` ni confirma una adopción real.
- HU02 exporta todas las filas para auditoría, incluidas las `indeterminada` junto con su motivo. HU03 las excluirá al construir la muestra de entrenamiento.
- `(id_ejecucion, id_mascota)` evita duplicar una mascota en una ejecución. El mismo SKU entre distintos CSV conserva la identidad e historial; no se debe cambiar ni reutilizar el SKU para otro animal.

## Despliegue mínimo

Separar configuración local, pruebas, staging y producción; PostgreSQL no se expone al navegador. HTTPS en despliegue; backup/restauración de DB y artefactos; health/readiness; logs estructurados sin credenciales ni datos personales. La ejecución programada es una capacidad futura: antes de habilitarla habrá que definir fuente, calendario y control de duplicados.
