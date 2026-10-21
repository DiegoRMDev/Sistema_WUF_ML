# HU03 — entrenamiento, evaluación y predicción

## Propósito y alcance

HU03 toma una versión auditable del Dataset Histórico HU02 para aprender a distinguir perfiles que **permanecen** en el catálogo de aquellos que **salen del catálogo**. Se implementa Random Forest con las librerías abiertas `scikit-learn`, `pandas` y `joblib`, ya definidas en la arquitectura del proyecto.

La interfaz conserva el término solicitado **“Probabilidad estimada de adopción”**. Esa cifra se calcula a partir de la clase positiva `salio_catalogo` de HU02; por ello es una estimación indirecta basada en la salida del catálogo. No confirma una adopción real ni se presenta como una probabilidad calibrada. Las métricas demo tampoco son evidencia de desempeño en adopciones reales.

## Acceso por rol e interfaz

- Recolección, Dataset Histórico y Entrenamiento se muestran solo al rol Analista. El frontend también bloquea la navegación directa a esas vistas; las rutas de lectura/escritura correspondientes verifican el rol en el backend.
- `GET /api/v1/models/predictions` acepta a cualquier usuario autenticado porque alimenta la sección Catálogo, que se comparte con Marketing y Área de Ayuda. Este permiso no da acceso al historial ni a las operaciones de entrenamiento/publicación.
- El historial ofrece **Ver** para consultar cualquier versión. Al entrenar, el panel de métricas, importancia y matriz cambia a la candidata recién creada; publicar sigue siendo una acción explícita.
- La fecha de entrenamiento se conserva como hora de Perú (`America/Lima`): el backend fija esa zona al guardar y la incluye en la respuesta de la API, para que el navegador no interprete una hora local sin zona como UTC.
- Catálogo consulta todos los perfiles del snapshot completo más reciente. El buscador por SKU/nombre y los filtros por estado/prioridad solo modifican las filas visibles; hay desplazamiento vertical y horizontal. La API relaciona las predicciones con esa ejecución y el modelo vigente.

## Validación local con el escenario controlado

En la prueba local de `escenario_hu02_variable_v3`, los conteos de PostgreSQL coinciden con los CSV de las semanas 40/41/42: 180/165/190 perfiles. El snapshot final contiene 190 SKU únicos (86 disponibles, 104 no disponibles y 0 sin publicar); se cotejaron sus atributos con el CSV final y no hubo diferencias. La cohorte HU02 sigue siendo de 108 registros: 66 `permanece` y 42 `salio_catalogo`.

El modelo vigente de esa prueba generó 86 predicciones, una por cada perfil disponible; no generó predicciones para perfiles no disponibles. Los atributos visibles de los 190 perfiles del snapshot final coincidieron con el CSV importado. Las altas incluidas en la última captura no se agregan retroactivamente a la cohorte inicial de HU02.

## Escenario sintético HU02/HU03

Se actualizaron los tres CSV de [`data/capturas/escenario_hu02_variable_v3/`](../data/capturas/escenario_hu02_variable_v3/README.md) y el generador [`scripts/generar_escenario_hu02_variable.py`](../scripts/generar_escenario_hu02_variable.py). Las altas tienen nombres plausibles y atributos variados; el generador preserva el escenario 180→165→190, la cohorte de 108 perfiles y sus 66/42 etiquetas, junto con las transiciones acordadas. El validador de HU01 aceptó las tres capturas sin rechazos.

Para que la clase `salio_catalogo` permita explicar el aprendizaje, los datos de demostración usan una asociación sintética moderada con edad, tamaño y condición especial, más variación aleatoria. La regla no usa raza, sexo, pelaje ni energía. No es evidencia empírica de WUF: la salida del catálogo sigue siendo un proxy que no verifica la adopción, y ninguna de estas asociaciones debe explicarse como causa.

Las métricas de este escenario son demostrativas: describen una partición pequeña de datos sintéticos y no deben presentarse como desempeño esperado con datos reales. Una muestra pequeña puede producir variaciones notables entre particiones; cada observación pesa mucho en el resultado. La importancia global se calcula sobre variables codificadas (por ejemplo, categorías de tamaño) y no demuestra causalidad; las asociaciones del escenario son sintéticas.

### Interpretación de métricas y criterio orientativo de publicación

Todas estas métricas tienen valores entre 0 y 1 (o entre 0 % y 100 %); cuanto más altas, mejor en general, pero cada una responde una pregunta distinta. Se evalúan sobre el grupo de prueba, que no se utilizó para ajustar el modelo:

- **Accuracy:** proporción de predicciones correctas entre todos los perfiles de prueba. Puede parecer alta si una clase es mucho más frecuente que la otra.
- **Precision:** entre los perfiles que el modelo clasifica como `salio_catalogo`, qué proporción realmente tiene esa etiqueta. Una Precision baja implica más falsas alarmas de salida.
- **Recall:** entre los perfiles que realmente tienen la etiqueta `salio_catalogo`, qué proporción detectó el modelo. Un Recall bajo implica más salidas que no detectó.
- **F1-score:** media armónica de Precision y Recall; ayuda a revisar el equilibrio entre ambas, especialmente cuando las clases no tienen el mismo tamaño.
- **Matriz de confusión:** muestra los aciertos y errores por clase. En esta implementación, las filas son etiquetas reales y las columnas predicciones, en orden `[permanece, salio_catalogo]`.

No existe un corte universal que vuelva aceptable a cualquier modelo. Para esta demostración se propone como **guía inicial de revisión**, no como regla estadística ni requisito aprobado por WUF: Accuracy de al menos 75 % (umbral que actualmente sí aplica la aplicación), y Precision, Recall y F1 de al menos 70 % para la clase `salio_catalogo`. Además, revisar la matriz, confirmar que ambas clases estén representadas en prueba y comparar Accuracy con una predicción base que siempre elija la clase mayoritaria. Si una métrica cae bajo la guía, investigar el tipo de error y el tamaño de muestra antes de publicar; no ocultar el resultado ni cambiar los datos para forzar el corte. El sistema hoy bloquea automáticamente solo por el umbral configurable de Accuracy; las otras métricas se muestran para decisión informada del Analista.

Para que la evaluación resulte más estable se necesitan más mascotas únicas, etiquetas fiables y una evaluación con datos de otro periodo. La etiqueta actual es salida del catálogo, no adopción verificada. Con los datos sintéticos pequeños, conservar la semilla reproducible, empezar probando 25–30 % para prueba y comparar opciones de árboles/profundidad sin escoger una configuración solo porque obtuvo la mayor puntuación en la misma partición. Estos parámetros son puntos de partida, no valores universalmente óptimos.

Cada vez que se regeneren o importen los CSV, hay que crear de nuevo el dataset HU02 y entrenar una versión nueva. Las versiones y artefactos ya guardados no se recalculan automáticamente a partir de los CSV modificados.

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
2. Para crear la base de demostración nueva desde pgAdmin, crea primero una base vacía `wuf_predict_v4` y ejecuta `backend/schema_wuf_predict_v4.sql`. Este archivo ya integra las estructuras HU03 en el esquema. No ejecutes después la migración, que queda para bases v2/v3 antiguas.
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
