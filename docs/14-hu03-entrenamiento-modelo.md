# HU03 — entrenamiento, evaluación y predicción

## Propósito y alcance

HU03 toma una versión auditable del Dataset Histórico HU02 para aprender a distinguir perfiles que **permanecen** en el catálogo de aquellos que **salen del catálogo**. Se implementa Random Forest con las librerías abiertas `scikit-learn`, `pandas` y `joblib`, ya definidas en la arquitectura del proyecto.

La interfaz conserva el término solicitado **“Probabilidad estimada de adopción”**. Esa cifra se calcula a partir de la clase positiva `salio_catalogo` de HU02; por ello es una estimación indirecta basada en la salida del catálogo. No confirma una adopción real ni se presenta como una probabilidad calibrada. Las métricas demo tampoco son evidencia de desempeño en adopciones reales.

## Acceso por rol e interfaz

- Recolección, Dataset Histórico y Entrenamiento se muestran solo al rol Analista. El frontend también bloquea la navegación directa a esas vistas; las rutas de lectura/escritura correspondientes verifican el rol en el backend.
- `GET /api/v1/models/predictions` acepta a cualquier usuario autenticado porque alimenta la sección Catálogo, que se comparte con Marketing y Área de Ayuda. Este permiso no da acceso al historial ni a las operaciones de entrenamiento/publicación.
- El historial ofrece **Ver** para consultar cualquier versión. Al entrenar, el panel de métricas, importancia y matriz cambia a la candidata recién creada; publicar sigue siendo una acción explícita.
- Catálogo consulta todos los perfiles del snapshot completo más reciente. El buscador por SKU/nombre y los filtros por estado/prioridad solo modifican las filas visibles; hay desplazamiento vertical y horizontal. La API relaciona las predicciones con esa ejecución y el modelo vigente.

## Validación local con el escenario controlado

En la prueba local de `escenario_hu02_variable_v3`, los conteos de PostgreSQL coinciden con los CSV de las semanas 40/41/42: 180/165/190 perfiles. El snapshot final contiene 190 SKU únicos (86 disponibles, 104 no disponibles y 0 sin publicar); se cotejaron sus atributos con el CSV final y no hubo diferencias. La cohorte HU02 sigue siendo de 108 registros: 66 `permanece` y 42 `salio_catalogo`.

El modelo vigente de esa prueba generó 86 predicciones, una por cada perfil disponible; no generó predicciones para perfiles no disponibles. Los atributos visibles de los 190 perfiles del snapshot final coincidieron con el CSV importado. Las altas incluidas en la última captura no se agregan retroactivamente a la cohorte inicial de HU02.

Una ejecución de demostración con 100 árboles, profundidad máxima 10, 30 % para prueba y semilla 42 obtuvo Accuracy 97,0 %, Precision 100,0 %, Recall 92,3 %, F1 96,0 % y matriz `[[20, 0], [1, 12]]` (75 filas de entrenamiento y 33 de prueba). Son resultados reproducibles de este conjunto pequeño y sintético, no métricas esperadas para datos de WUF.

## Mejora pendiente de los CSV de demostración

Antes de usar HU03 como una demostración representativa, revisar los CSV de [`data/capturas/escenario_hu02_variable_v3/`](../data/capturas/escenario_hu02_variable_v3/README.md) y su generador [`scripts/generar_escenario_hu02_variable.py`](../scripts/generar_escenario_hu02_variable.py):

- Reemplazar nombres genéricos como `Mascota demo 199` por nombres verosímiles de mascotas, consistentes entre capturas para el mismo SKU. Seguirán siendo datos sintéticos, no fichas reales.
- Hacer más variadas y coherentes las combinaciones de atributos de los perfiles, evitando que el resultado dependa demasiado de una relación artificial entre la etiqueta y una variable como `orden_publicacion`.
- Volver a ejecutar HU01 y HU02 después de los cambios y comprobar que los conteos y transiciones semanales acordados se conservan. Reentrenar y describir las métricas que resulten de los datos; no modificar los perfiles para forzar una puntuación objetivo.

Este trabajo está pendiente de revisión con el usuario. Hasta completarlo, la importancia global y las métricas del escenario se deben explicar como una prueba controlada, no como evidencia de desempeño real.

## Preparación de datos y modelo

- El Analista elige una versión de dataset persistida en PostgreSQL. El entrenamiento lee sus detalles y los atributos del snapshot inicial; no modifica ni reexporta el CSV de auditoría de HU02.
- Se excluyen las filas `indeterminada`. Se guardan la cantidad excluida y sus motivos. Si quedan menos de 20 filas, falta una de las dos clases o la partición pierde una clase, se informa el problema y no se guarda una versión entrenada.
- Las variables usan atributos conocidos al inicio del seguimiento: especie, raza, sexo, edad en meses, indicadores de estimación, pelaje, tamaño, energía, condición especial y orden de publicación. Se omiten SKU/nombre como identificadores, descripción libre, URL y estados futuros para no revelar al modelo la etiqueta que debe aprender.
- `pandas` organiza las observaciones tabulares. El pipeline de `scikit-learn` completa edades faltantes con la mediana, valores categóricos faltantes con el valor más frecuente, codifica categorías con One-Hot Encoding y tolera categorías nuevas.
- Random Forest usa cantidad configurable de árboles, profundidad máxima opcional, balance de clases y semilla reproducible. Gini evalúa las separaciones; `max_features=sqrt` y bootstrap aportan variedad entre árboles. El porcentaje de prueba también es seleccionable. `GroupShuffleSplit` separa por SKU para mantener cada mascota en un solo grupo.
- La matriz de confusión conserva el orden `[permanece, salio_catalogo]` para filas reales y columnas predichas. Accuracy mide aciertos totales; Precision mide qué proporción de salidas señaladas realmente salió; Recall mide cuántas salidas observadas detectó; F1 resume el balance entre Precision y Recall. Se calculan con el grupo de prueba separado.
- La importancia global de atributos se presenta como referencia exploratoria, no como explicación causal. `predict_proba` no está calibrada; los porcentajes sirven para ordenar y revisar, no para prometer una tasa individual exacta.

## Umbral, publicación y predicciones

El modelo candidato se guarda como `publicable` si Accuracy alcanza el umbral configurado; si no, se conserva como `no_publicable` y no se activa. Un modelo publicable no reemplaza por sí solo al vigente: el Analista elige **Publicar y predecir** después de revisar sus métricas. La activación comprueba el SHA-256 del artefacto antes de cargarlo.

Al publicarse, el pipeline calcula la probabilidad de la clase positiva `salio_catalogo` para cada mascota `disponible` de la captura completa más reciente. Guarda probabilidad, prioridad, fecha, versión y ejecución fuente en `prediccion`. La prioridad alta corresponde a una estimación menor; los cortes iniciales son configurables por entorno y se muestran como bandas demo, pendientes de validación con WUF.

La pantalla Catálogo consulta las mascotas de la captura completa vigente y solo muestra predicciones ligadas a esa misma ejecución. Las no disponibles no reciben predicción; si no existe un modelo vigente o la última captura todavía no fue evaluada, muestra el catálogo sin inventar probabilidades. Tras importar una nueva captura, el Analista usa **Actualizar predicciones** desde el historial del modelo vigente.

## Artefactos y trazabilidad

`joblib` serializa el pipeline ya entrenado para conservar junto el preprocesamiento y el clasificador. El archivo se guarda en `MODEL_ARTIFACT_DIR` fuera de `frontend/public/`, con un nombre generado por el backend. Se registra su hash SHA-256 y el backend lo verifica antes de deserializarlo. No se aceptan archivos de modelo desde el navegador, porque un archivo Joblib puede ejecutar código al cargarse.

En `modelo_predictivo` se guardan versión, dataset, métricas, clase positiva, conteos de entrenamiento/prueba/exclusión, umbral, matriz, importancia, hiperparámetros, semilla, tamaño de prueba, conteo de clases, motivos de exclusión y versiones de scikit-learn, pandas y joblib. La API no devuelve la ruta local del artefacto.

## Comentarios didácticos en backend

Los archivos `backend/app/domain/model_training.py`, `backend/app/services/model_service.py`, `backend/app/infrastructure/model_artifact_storage.py` y `backend/app/infrastructure/model_repository.py` comentan el propósito de cada parte principal: preparar atributos para que el modelo los entienda, proteger la evaluación de las mismas mascotas, interpretar las métricas, conservar la transformación junto al clasificador y dejar resultados reproducibles. Los comentarios describen el objetivo del paso y el flujo en lenguaje breve, sin parafrasear cada línea.

## API HU03

| Método y ruta | Uso | Permiso |
|---|---|---|
| `GET /api/v1/models/options` | Versiones de dataset disponibles y parámetros iniciales | Analista |
| `POST /api/v1/models/train` | Entrenar y registrar un candidato | Analista |
| `GET /api/v1/models` | Historial, métricas y estados | Analista |
| `POST /api/v1/models/{id}/activate` | Publicar explícitamente y generar predicciones | Analista |
| `POST /api/v1/models/{id}/refresh-predictions` | Actualizar predicciones con una captura más reciente y el modelo vigente | Analista |
| `GET /api/v1/models/predictions` | Catálogo con predicciones vigentes | Usuario autenticado |

## Configuración inicial en Windows

1. Haz una copia de seguridad de PostgreSQL.
2. Con pgAdmin, conéctate a la base de trabajo v2/v3 (para este proyecto, `wuf_predict_v3`), abre Query Tool y ejecuta **una sola vez** `backend/upgrade_hu03_ml.sql`. No ejecutes nuevamente el esquema completo.
3. Desde PowerShell entra a `backend/`, activa `.venv` y actualiza las dependencias del proyecto:

   ```powershell
   python -m pip install -e .
   python -m pip check
   ```

4. Revisa `backend/.env`. Los valores iniciales quedan en `.env.example`; puedes añadir o ajustar:

   ```dotenv
   MODEL_ARTIFACT_DIR=../artifacts/models
   MODEL_MIN_ACCURACY=0.75
   MODEL_DEFAULT_TEST_SIZE=0.2
   MODEL_DEFAULT_ESTIMATORS=300
   MODEL_RANDOM_SEED=42
   MODEL_PRIORITY_HIGH_MAX=0.35
   MODEL_PRIORITY_MEDIUM_MAX=0.65
   ```

   Las dos bandas de prioridad y el 75% son valores configurables de demostración; no son umbrales operativos aprobados por WUF. `MODEL_ARTIFACT_DIR` debe permanecer fuera de `frontend/public/`.
5. Reinicia el backend para que cargue dependencias, variables y el esquema actualizado. El backend verifica al iniciar que la migración HU03 está aplicada en v2/v3.
6. Inicia el frontend e ingresa con el rol Analista. En **Entrenamiento**, elige el dataset, ajusta la proporción de prueba y los árboles, y pulsa **Entrenar nueva versión**.
7. Revisa tamaño de los grupos, motivos excluidos, métricas y matriz. Usa **Ver** en el historial para consultar otra versión. Si el candidato supera el umbral, publícalo desde el historial. Abre **Catálogo** para consultar las predicciones del modelo vigente.

El entrenamiento usa un split de prueba, no validación cruzada. Con el conjunto demo pequeño, las métricas pueden variar bastante según la partición. Si no existe una clase suficiente para la prueba o el modelo no supera el umbral, la aplicación lo explica y no permite publicarlo.
