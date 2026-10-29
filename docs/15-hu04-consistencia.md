# HU04 — evaluación de consistencia del catálogo

## Propósito y límite metodológico

HU04 prioriza qué perfiles disponibles conviene verificar primero. Sigue el prototipo: usa un árbol de decisión, muestra niveles bajo/medio/alto y presenta las condiciones que llevaron a cada resultado. Estos niveles son **prioridades de revisión**; no confirman que el estado publicado sea incorrecto.

Los CSV describen el catálogo publicado, pero no confirman el estado real de la mascota en el albergue. Por eso la versión actual genera prioridades provisionales mediante una regla operativa aplicada al historial de snapshots. La regla asigna la prioridad operativa; el árbol aprende a aproximarla y permite inspeccionar sus métricas, reglas e importancias. Sus métricas no validan la detección de inconsistencias reales. Cuando se registren verificaciones humanas independientes, se podrán reemplazar estas etiquetas y medir el desempeño con evidencia real.

## Datos y etiqueta provisional

El entrenamiento recorre ejecuciones de recolección completas en orden cronológico. Cada perfil disponible en cada captura puede aportar una observación. Una ausencia, un estado distinto de `disponible` o un salto entre capturas reinicia el conteo de disponibilidad consecutiva.

La regla versionada `prioridad_revision_hu04_v2` se aplica a mascotas disponibles. Usa la antigüedad desde `fecha_publicacion` y la persistencia del estado disponible en capturas completas consecutivas:

| Prioridad | Regla |
|---|---|
| Alto | Disponible en al menos 3 capturas semanales consecutivas y publicado hace al menos 180 días. |
| Medio | No cumple la regla alta y lleva disponible en al menos 2 capturas consecutivas o fue publicado hace al menos 60 días. |
| Bajo | No cumple las reglas anteriores. Indica baja prioridad con la evidencia disponible, no garantiza que el perfil esté actualizado. |

Una ausencia en un CSV completo o un estado distinto de disponible reinicia la secuencia. Para contar como consecutivas, dos capturas deben tener fechas distintas y estar separadas por 1 a 14 días; una ausencia de varias semanas o capturas repetidas de la misma fecha no aumentan la permanencia. El intervalo máximo es configuración interna del backend. Los umbrales son supuestos operativos iniciales, no políticas confirmadas del albergue.

| Dato derivado | Fuente y cálculo | Uso |
|---|---|---|
| Días desde publicación | `fecha_captura` menos `fecha_publicacion` del snapshot | Predictor |
| Capturas consecutivas disponible | Secuencia cronológica de `estado_detectado = disponible`, reiniciada por ausencia, otro estado o intervalo inválido | Predictor |
| Capturas observadas | Cantidad de capturas donde existe un snapshot del SKU, aunque su estado sea no disponible | Auditoría; excluido de los predictores |

El escenario actual de CSV es `escenario_hu02_variable_v4`. Sus transiciones y fechas de publicación conservan el escenario v3; para la captura final hay 86 perfiles disponibles. La distribución de prioridades depende de los parámetros de HU04 y es una referencia de demostración, no una medición de exactitud real.

## Entrenamiento y evaluación

Se utiliza `DecisionTreeClassifier` de scikit-learn con criterio Gini, mínimo de 3 observaciones por hoja, balance de clases y semilla reproducible. Las únicas variables predictoras son días desde publicación y capturas consecutivas disponible, las mismas señales que fundamentan la regla. Capturas observadas se conserva como dato de auditoría, pero no se usa para predecir porque cuenta también registros no disponibles. El Analista puede seleccionar profundidad máxima entre 1 y 4 (por defecto 3) y porcentaje para prueba de 20 %, 25 % o 30 % (por defecto 25 %). La profundidad 3 es un valor inicial para representar las condiciones de prioridad, pero no garantiza que el árbol aprenda umbrales exactos cuando el historial no contiene ejemplos en esos límites. Profundidades menores pueden simplificarlas. El porcentaje modifica cuántos grupos SKU quedan reservados para evaluar. El SKU no se usa como predictor. No se permite cambiar la semilla desde la interfaz para conservar comparaciones reproducibles.

La partición de prueba se realiza por grupos de SKU para que una mascota no aparezca a ambos lados. Se presentan Accuracy, F1 macro, matriz de confusión, contribución Gini de las variables predictoras, reglas y diagrama del árbol final. La contribución Gini describe cuánto reducen la impureza las divisiones de cada variable; no representa causalidad ni una importancia para el estado real. Después de medir la partición, el árbol comparativo se ajusta con todo el historial disponible; la regla sigue asignando la prioridad del catálogo. Toda versión conserva los parámetros, variables, versión de regla y comparación frente a la regla. Las versiones creadas antes de este cambio pueden reflejar la predicción del árbol como prioridad guardada; las versiones nuevas indican la fuente en `indicadores.fuente_prioridad`. El panel y el historial identifican explícitamente el modelo vigente; al consultar una versión antigua se indica que es histórica y no vigente.

Aunque la separación por SKU evita mezclar una mascota entre entrenamiento y prueba, las etiquetas se derivan de las mismas variables que recibe el árbol. Por tanto, métricas altas (incluso 100 %) solo indican que el árbol reproduce la regla provisional. Para evaluar detección real se necesitan verificaciones humanas independientes. Los límites de prioridad tampoco deben interpretarse como una probabilidad calibrada.

### Cómo leer los resultados

- **Accuracy**: proporción de observaciones de prueba cuya prioridad el árbol clasificó correctamente. Por ejemplo, 94 % significa que acertó aproximadamente 94 de cada 100 observaciones de prueba.
- **F1 macro**: calcula el F1 de prioridad baja, media y alta por separado y luego promedia los tres valores. Así una clase frecuente como `medio` no oculta por sí sola un resultado peor en `bajo` o `alto`.
- **Matriz de confusión**: las filas son la prioridad de referencia de la regla y las columnas son la prioridad predicha por el árbol, en el orden bajo, medio y alto. Los valores de la diagonal son aciertos; los demás muestran qué niveles confundió.
- **Coincidencia en la última captura**: compara por separado el árbol con la regla en los perfiles disponibles actuales. No forma parte de la matriz de prueba. Aunque haya diferencias, la prioridad mostrada a Operaciones/Revisión sigue siendo la de la regla.
- **Contribución de variables**: refleja cuánto redujeron la impureza Gini las divisiones del árbol. No mide causalidad ni demuestra que una característica provoque adopciones o desactualizaciones.

Las opciones de profundidad (1–4) controlan cuántas divisiones puede aprender el árbol: una profundidad mayor puede representar más condiciones, pero también ajustarse demasiado a los datos disponibles. El porcentaje para prueba (20 %, 25 % o 30 %) reserva grupos de mascotas para evaluación; el resto se usa para entrenar. Se recomienda comenzar con profundidad 3 y prueba 25 % para estos CSV, y comparar opciones manteniendo la semilla 42. La mejor métrica no convierte las prioridades sintéticas en evidencia real.

Una comprobación en memoria con las capturas actuales, usando solo las dos variables predictoras y profundidad 3, reprodujo las 68 filas de prueba (Accuracy y F1 macro 100 %; matriz diagonal 3/54/11) y las prioridades actuales (57 altas, 9 medias, 20 bajas). Sin embargo, con combinaciones no representadas en esos CSV, el árbol no siempre reproduce la regla: con 40 días y 2 capturas disponibles predijo bajo (la regla indica medio); con 180 días y 3 capturas disponibles predijo medio (la regla indica alto). Por ello, el árbol no decide la prioridad operativa: el servicio aplica directamente la regla versionada en cualquier combinación y persiste por separado la predicción del árbol para comparar. La partición por SKU sigue midiendo cuánto reproduce el árbol la regla en los datos disponibles, pero no valida generalización ni detección real.

La pantalla de evaluación HU04 muestra la prioridad calculada por la regla v2. El resultado del árbol se guarda en `indicadores.prediccion_arbol`; `indicadores.coincide_arbol_regla` registra si coincide con la prioridad de regla. Los metadatos de cada modelo incluyen coincidencias y diferencias del árbol frente a la regla para los perfiles disponibles de la captura evaluada. La importancia Gini y las reglas del diagrama describen el árbol, no alteran las prioridades que ve el usuario.

El servicio aplica la regla a los perfiles disponibles de la captura completa más reciente y persiste la prioridad y su justificación por perfil. También guarda la predicción y el camino explicativo del árbol como evidencia comparativa. El artefacto se guarda con `joblib` en `MODEL_ARTIFACT_DIR/consistency`, separado de los modelos HU03, y se registra su hash SHA-256.

## Interfaz, permisos y persistencia

- La sección **Entrenamiento** conserva el Random Forest HU03 y añade la tarjeta del árbol HU04, sus métricas, matriz, contribución de variables, reglas y versiones. La navegación y el cambio de sección restringen Entrenamiento al rol Analista, y la API vuelve a comprobar el permiso en `POST /api/v1/consistency/train`; **solo Analista puede crear versiones**.
- HU04 conserva métricas, diagrama, reglas y el historial de árboles en **Entrenamiento**. La consulta y atención de las alertas altas ya corresponde a la bandeja HU07.
- Al guardar la evaluación, HU07 genera o actualiza alertas internas de prioridad alta a partir de la regla operativa; no usa la predicción del árbol como único criterio para notificar. Las alertas se explican como solicitudes de revisión, no como fallos confirmados.
- `modelo_consistencia` conserva versiones, parámetros y métricas; `evaluacion_consistencia` relaciona árbol, mascota, snapshot y ejecución, junto con los indicadores y la justificación.
- `evaluacion_consistencia.indicadores` conserva en JSONB las variables, `dias_sin_cambio_observado`, la predicción del árbol y la comparación con la regla. Los días se cuentan desde el inicio de la secuencia disponible observada en los CSV; no prueban el historial real de WUF.
- El esquema limpio v5 mantiene la regla actual `prioridad_revision_hu04_v2`, enlaza alertas con las evaluaciones y guarda acciones humanas en `alerta_atencion`. Consulta [`04-modulos-hu.md`](04-modulos-hu.md) para el ciclo HU07.

## API

| Método y ruta | Uso | Permiso |
|---|---|---|
| `POST /api/v1/consistency/train` | Crear una versión con `profundidad_maxima` (1–4) y `proporcion_prueba` (0.20, 0.25 o 0.30) opcionales; evaluar el árbol y aplicar la regla a la última captura completa | Analista |
| `GET /api/v1/consistency/latest` | Consultar árbol vigente y evaluaciones más recientes | Analista, Área de Ayuda |
| `GET /api/v1/consistency/history/{model_id}` | Consultar métricas y evaluaciones de una versión anterior | Analista, Área de Ayuda |

## Instalación de la extensión

Para HU07 crea una base nueva y vacía `wuf_predict_v7`, y ejecuta desde pgAdmin **solo** `backend/schema_wuf_predict_v5.sql`. Este instalador integra HU01–HU07; no lo ejecutes sobre la base v6 ni apliques upgrades a la instalación nueva.

Los scripts `upgrade_hu04_*.sql` se conservan para bases históricas que necesiten esos cambios; no se aplican a la instalación limpia v5.

Los parámetros opcionales son:

```dotenv
CONSISTENCY_TEST_SIZE=0.25
CONSISTENCY_RANDOM_SEED=42
CONSISTENCY_MAX_DEPTH=3
CONSISTENCY_HIGH_MIN_CAPTURES=3
CONSISTENCY_HIGH_MIN_AGE_DAYS=180
CONSISTENCY_MEDIUM_MIN_CAPTURES=2
CONSISTENCY_MEDIUM_MIN_AGE_DAYS=60
CONSISTENCY_MAX_CAPTURE_GAP_DAYS=14
```

Con al menos tres capturas completas, ingresa como Analista a **Entrenamiento**, selecciona profundidad y porcentaje de prueba, y pulsa **Entrenar árbol y evaluar catálogo**. La evaluación queda en HU04 y las prioridades altas se generan/actualizan en **Alertas de desactualización**. Cada entrenamiento crea una versión nueva; las anteriores se conservan para consulta.

La base anterior `wuf_predict_v6` usa esquema v4 y no tiene las tablas de atención HU07; el código nuevo requiere que `DATABASE_URL` apunte a `wuf_predict_v7` con esquema v5.

## Pendiente para validar con datos reales

El Área de Ayuda debe registrar la verificación independiente de una muestra de perfiles, por ejemplo estado correcto/obsoleto y fecha de revisión. Con esas etiquetas se podrá reemplazar `prioridad_revision_hu04_v2`, medir falsos positivos y falsos negativos y revisar los umbrales antes de interpretar HU04 como detección real. Hasta entonces, el resultado es una prioridad de revisión de demostración, no una afirmación sobre el estado real de una mascota. HU07 atiende alertas internas generadas por prioridades altas; todavía no hay notificación externa.
