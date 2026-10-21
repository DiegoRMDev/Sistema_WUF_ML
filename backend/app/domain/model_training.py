"""Preparación y evaluación del clasificador de adopción estimada para HU03."""

from dataclasses import dataclass
from importlib.metadata import version as installed_version
from typing import Any

# pandas organiza las filas SQL en columnas para limpiar atributos sin alterar el dataset guardado.
import pandas as pd
# scikit-learn prepara variables, crea particiones, entrena el bosque y mide su resultado.
import sklearn
# ColumnTransformer y Pipeline conectan limpieza y predicción para repetir el mismo flujo.
from sklearn.compose import ColumnTransformer
# RandomForestClassifier aprende las reglas combinando varios árboles.
from sklearn.ensemble import RandomForestClassifier
# SimpleImputer completa valores faltantes sin eliminar filas útiles.
from sklearn.impute import SimpleImputer
# Las métricas y la matriz resumen los aciertos sobre perfiles apartados para prueba.
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
# GroupShuffleSplit mantiene todas las filas de una mascota en un solo lado de la evaluación.
from sklearn.model_selection import GroupShuffleSplit
# Pipeline aplica el mismo preprocesamiento cuando entrena y cuando predice.
from sklearn.pipeline import Pipeline
# OneHotEncoder transforma categorías de texto en columnas que el clasificador puede usar.
from sklearn.preprocessing import OneHotEncoder


# Solo se usan atributos disponibles al inicio del seguimiento; SKU/nombre identifican
# registros y los estados posteriores revelarían directamente la respuesta del modelo.
NUMERIC_FEATURES = [
    "edad_meses", "edad_estimada", "tamano_estimado", "condicion_especial", "orden_publicacion"
]
CATEGORICAL_FEATURES = [
    "especie", "raza", "sexo", "tipo_pelaje", "tamano", "nivel_energia"
]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
LABEL_TO_NUMBER = {"permanece": 0, "salio_catalogo": 1}


class ModelTrainingError(ValueError):
    """Describe datos insuficientes o inconsistentes que impiden entrenar."""


@dataclass(frozen=True, slots=True)
class TrainingResult:
    pipeline: Pipeline
    metrics: dict[str, float]
    confusion: list[list[int]]
    feature_importance: list[dict[str, float | str]]
    train_count: int
    test_count: int
    excluded_count: int
    excluded_reasons: dict[str, int]
    class_counts: dict[str, int]
    parameters: dict[str, Any]


def _prepare_features(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convierte los atributos de PostgreSQL en una tabla apta para el pipeline."""
    frame = pd.DataFrame(rows)
    missing = set(FEATURE_COLUMNS + ["sku", "etiqueta_catalogo"]) - set(frame.columns)
    if missing:
        raise ModelTrainingError("El dataset no contiene las columnas requeridas para entrenar.")

    # Los valores faltantes se dejan como nulos para que los imputadores los traten
    # de manera consistente tanto durante la evaluación como en futuras predicciones.
    frame = frame.copy()
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].map(
            lambda value: value.strip() if isinstance(value, str) and value.strip() else None
        )
    return frame


def _build_pipeline(n_estimators: int, max_depth: int | None, seed: int) -> Pipeline:
    """Empaqueta limpieza, codificación y Random Forest para reutilizar el mismo flujo."""
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore")),
    ])
    preparation = ColumnTransformer([
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
    ])

    # Cada árbol aprende reglas con muestras y atributos variados; la votación
    # conjunta suele ser más estable que depender de un único árbol.
    classifier = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        # Gini mide la pureza de cada separación; sqrt y bootstrap diversifican los árboles.
        criterion="gini",
        max_features="sqrt",
        bootstrap=True,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    return Pipeline([("preprocessing", preparation), ("classifier", classifier)])


def train_random_forest(
    rows: list[dict[str, Any]], *, test_size: float, n_estimators: int,
    max_depth: int | None, seed: int,
) -> TrainingResult:
    """Filtra filas no utilizables, separa mascotas y calcula resultados del modelo."""
    frame = _prepare_features(rows)
    excluded = frame[frame["etiqueta_catalogo"] == "indeterminada"]
    usable = frame[frame["etiqueta_catalogo"].isin(LABEL_TO_NUMBER)].copy()
    unknown = frame[~frame["etiqueta_catalogo"].isin([*LABEL_TO_NUMBER, "indeterminada"])]
    if not unknown.empty:
        raise ModelTrainingError("El dataset contiene etiquetas desconocidas; regenera o revisa HU02.")

    class_counts = usable["etiqueta_catalogo"].value_counts().to_dict()
    if len(usable) < 20 or set(class_counts) != set(LABEL_TO_NUMBER):
        raise ModelTrainingError("Se requieren al menos 20 filas utilizables y ejemplos de ambas etiquetas.")
    if min(class_counts.values()) < 2:
        raise ModelTrainingError("Se requieren al menos dos mascotas por etiqueta para evaluar el modelo.")

    features = usable[FEATURE_COLUMNS]
    target = usable["etiqueta_catalogo"].map(LABEL_TO_NUMBER).astype("int8")
    groups = usable["sku"].astype(str)

    # Separar por SKU evita evaluar una mascota con datos de otra versión del mismo
    # perfil presentes en entrenamiento. El resto se reserva para entrenar el bosque.
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_indices, test_indices = next(splitter.split(features, target, groups=groups))
    y_train, y_test = target.iloc[train_indices], target.iloc[test_indices]
    if y_train.nunique() != 2 or y_test.nunique() != 2:
        raise ModelTrainingError(
            "La partición dejó una etiqueta fuera de entrenamiento o prueba; cambia la proporción o la semilla."
        )

    pipeline = _build_pipeline(n_estimators, max_depth, seed)
    pipeline.fit(features.iloc[train_indices], y_train)
    predicted = pipeline.predict(features.iloc[test_indices])

    # Métricas calculadas sobre perfiles que el modelo no usó para aprender.
    # Accuracy resume aciertos; Precision indica cuántas salidas señaladas realmente salieron;
    # Recall mide cuántas salidas reales detecta el modelo; F1 equilibra Precision y Recall.
    metrics = {
        "accuracy": float(accuracy_score(y_test, predicted)),
        "precision": float(precision_score(y_test, predicted, pos_label=1, zero_division=0)),
        "recall": float(recall_score(y_test, predicted, pos_label=1, zero_division=0)),
        "f1": float(f1_score(y_test, predicted, pos_label=1, zero_division=0)),
    }
    confusion = confusion_matrix(y_test, predicted, labels=[0, 1]).tolist()

    # Esta lista describe qué atributos ayudaron globalmente al bosque; no demuestra causalidad.
    names = pipeline.named_steps["preprocessing"].get_feature_names_out()
    values = pipeline.named_steps["classifier"].feature_importances_
    importance = sorted(
        ({"feature": str(name), "importance": float(value)} for name, value in zip(names, values, strict=True)),
        key=lambda item: float(item["importance"]), reverse=True,
    )[:15]
    reasons = excluded.get("motivo_indeterminado", pd.Series(dtype="object"))
    excluded_reasons = {str(key): int(value) for key, value in reasons.fillna("sin_motivo").value_counts().items()}

    return TrainingResult(
        pipeline=pipeline,
        metrics=metrics,
        confusion=confusion,
        feature_importance=importance,
        train_count=len(train_indices),
        test_count=len(test_indices),
        excluded_count=len(excluded),
        excluded_reasons=excluded_reasons,
        class_counts={str(key): int(value) for key, value in class_counts.items()},
        parameters={
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "criterion": "gini",
            "max_features": "sqrt",
            "bootstrap": True,
            "test_size": test_size,
            "random_state": seed,
            "class_weight": "balanced",
            "split": "GroupShuffleSplit por SKU",
            "library_versions": {
                "scikit-learn": sklearn.__version__,
                "pandas": pd.__version__,
                "joblib": installed_version("joblib"),
            },
        },
    )
