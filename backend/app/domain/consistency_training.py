"""Entrena y explica el árbol demo de consistencia HU04."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# pandas organiza las observaciones de snapshots como una tabla de variables.
import pandas as pd
# scikit-learn separa por mascota, entrena el árbol y calcula métricas de evaluación.
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
# El árbol genera niveles de riesgo y permite mostrar las condiciones de cada decisión.
from sklearn.tree import DecisionTreeClassifier, export_text

# Solo estas dos señales definen la prioridad acordada; las apariciones totales
# se conservan como contexto de auditoría, pero no participan en la predicción.
FEATURES = ["dias_publicacion", "capturas_disponible"]
FEATURE_LABELS = {
    "dias_publicacion": "días desde publicación",
    "capturas_disponible": "capturas consecutivas disponible",
}
RISK_LEVELS = ["bajo", "medio", "alto"]


class ConsistencyTrainingError(ValueError):
    """Datos insuficientes para entrenar o evaluar el árbol de HU04."""


@dataclass(frozen=True, slots=True)
class ConsistencyTrainingResult:
    estimator: DecisionTreeClassifier
    metrics: dict[str, float]
    confusion: list[list[int]]
    feature_importance: list[dict[str, float | str]]
    train_count: int
    test_count: int
    class_counts: dict[str, int]
    parameters: dict[str, Any]
    tree_rules: str
    tree_diagram: dict[str, Any]


def _as_date(value: date | datetime | str) -> date:
    """Normaliza valores de fecha provenientes de PostgreSQL para calcular antigüedad."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def build_proxy_samples(
    timeline: list[dict[str, Any]],
    *,
    high_min_captures: int,
    high_min_age_days: int,
    medium_min_captures: int,
    medium_min_age_days: int,
    max_capture_gap_days: int,
) -> list[dict[str, Any]]:
    """Convierte snapshots en filas y prioridades provisionales de revisión.

    Las etiquetas son una política de triage basada en evidencia del catálogo; no
    representan una verdad real ni confirman que el estado publicado sea incorrecto.
    """
    if not timeline:
        return []

    runs = sorted({
        (_as_date(row["fecha_captura"]), int(row["id_ejecucion"])) for row in timeline
    })
    snapshots_by_run: dict[tuple[date, int], dict[str, dict[str, Any]]] = {
        run_key: {} for run_key in runs
    }
    for row in timeline:
        run_key = (_as_date(row["fecha_captura"]), int(row["id_ejecucion"]))
        snapshots_by_run[run_key][str(row["sku"])] = row

    all_skus = sorted({str(row["sku"]) for row in timeline})
    available_streak: dict[str, int] = {sku: 0 for sku in all_skus}
    observed_count: dict[str, int] = {sku: 0 for sku in all_skus}
    last_available_date: dict[str, date | None] = {sku: None for sku in all_skus}
    samples: list[dict[str, Any]] = []

    # Recorre las capturas en orden calendario para medir permanencia sin mirar al futuro.
    for capture_date, execution_id in runs:
        current = snapshots_by_run[(capture_date, execution_id)]
        for sku in all_skus:
            row = current.get(sku)
            if row is None:
                available_streak[sku] = 0
                last_available_date[sku] = None
                continue
            observed_count[sku] += 1
            state = str(row.get("estado_detectado", "")).casefold()
            if state != "disponible":
                available_streak[sku] = 0
                last_available_date[sku] = None
                continue

            # Un hueco largo rompe la continuidad: tres CSV separados por meses no
            # equivalen a tres capturas semanales consecutivas.
            previous_date = last_available_date[sku]
            if previous_date is not None:
                gap_days = (capture_date - previous_date).days
                if gap_days < 1 or gap_days > max_capture_gap_days:
                    available_streak[sku] = 0
            available_streak[sku] += 1
            last_available_date[sku] = capture_date
            publication_age = max(
                0, (capture_date - _as_date(row["fecha_publicacion"])).days
            )
            features = {
                "dias_publicacion": publication_age,
                "capturas_disponible": available_streak[sku],
                "capturas_observadas": observed_count[sku],
            }
            proxy_label = review_priority(
                features,
                high_min_captures=high_min_captures,
                high_min_age_days=high_min_age_days,
                medium_min_captures=medium_min_captures,
                medium_min_age_days=medium_min_age_days,
            )
            samples.append({
                **row, **features, "etiqueta_proxy": proxy_label,
                "id_ejecucion": execution_id,
            })
    return samples


def review_priority(
    features: dict[str, Any],
    *,
    high_min_captures: int,
    high_min_age_days: int,
    medium_min_captures: int,
    medium_min_age_days: int,
) -> str:
    """Aplica exactamente la política acordada, sin depender del árbol aproximado."""
    streak = int(features["capturas_disponible"])
    publication_age = int(features["dias_publicacion"])
    if streak >= high_min_captures and publication_age >= high_min_age_days:
        return "alto"
    if streak >= medium_min_captures or publication_age >= medium_min_age_days:
        return "medio"
    return "bajo"


def explain_review_priority(
    priority: str,
    features: dict[str, Any],
    *,
    high_min_captures: int,
    high_min_age_days: int,
    medium_min_captures: int,
    medium_min_age_days: int,
) -> str:
    """Explica la prioridad final con los umbrales de la regla, no con el árbol."""
    streak = int(features["capturas_disponible"])
    publication_age = int(features["dias_publicacion"])
    if priority == "alto":
        return (
            f"Prioridad alta: disponible en {streak} capturas consecutivas "
            f"y publicada hace {publication_age} días."
        )
    if priority == "medio":
        reasons = []
        if streak >= medium_min_captures:
            reasons.append(f"disponible en {streak} capturas consecutivas")
        if publication_age >= medium_min_age_days:
            reasons.append(f"publicada hace {publication_age} días")
        evidence = " y ".join(reasons)
        return f"Prioridad media: {evidence}; se recomienda revisar el perfil."
    return (
        "Prioridad baja: todavía no cumple los criterios de permanencia "
        "o antigüedad para priorizar su revisión."
    )


def train_decision_tree(
    samples: list[dict[str, Any]],
    *,
    test_size: float,
    random_seed: int,
    max_depth: int,
) -> ConsistencyTrainingResult:
    """Evalúa por mascota y ajusta el árbol final con las filas disponibles."""
    frame = pd.DataFrame(samples)
    required = set(FEATURES + ["sku", "etiqueta_proxy"])
    if frame.empty or not required.issubset(frame.columns):
        raise ConsistencyTrainingError("No hay historial suficiente para preparar la evaluación.")

    frame = frame.dropna(subset=FEATURES + ["sku", "etiqueta_proxy"]).copy()
    counts = frame["etiqueta_proxy"].value_counts().to_dict()
    if len(frame) < 30 or set(counts) != set(RISK_LEVELS):
        raise ConsistencyTrainingError(
            "Se requieren al menos 30 observaciones y ejemplos de riesgo bajo, medio y alto."
        )
    if frame.groupby("etiqueta_proxy")["sku"].nunique().min() < 2:
        raise ConsistencyTrainingError("Cada nivel de riesgo necesita ejemplos de al menos dos mascotas.")

    features = frame[FEATURES].astype("float64")
    labels = frame["etiqueta_proxy"].astype(str)
    groups = frame["sku"].astype(str)
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_seed)
    train_idx, test_idx = next(splitter.split(features, labels, groups=groups))
    y_train, y_test = labels.iloc[train_idx], labels.iloc[test_idx]
    if set(y_train) != set(RISK_LEVELS) or set(y_test) != set(RISK_LEVELS):
        raise ConsistencyTrainingError(
            "La partición dejó un nivel de riesgo fuera de entrenamiento o prueba."
        )

    # Este árbol pequeño hace explícitas las reglas de la demo y limita su complejidad.
    evaluation_tree = DecisionTreeClassifier(
        criterion="gini",
        max_depth=max_depth,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=random_seed,
    )
    evaluation_tree.fit(features.iloc[train_idx], y_train)
    predicted = evaluation_tree.predict(features.iloc[test_idx])

    # Métricas separadas muestran aciertos globales y equilibrio entre los tres riesgos.
    metrics = {
        "accuracy": float(accuracy_score(y_test, predicted)),
        "f1_macro": float(f1_score(y_test, predicted, labels=RISK_LEVELS, average="macro", zero_division=0)),
    }
    confusion = confusion_matrix(y_test, predicted, labels=RISK_LEVELS).tolist()

    # Después de medir el resultado, se ajusta el modelo final con todo el historial disponible.
    final_tree = DecisionTreeClassifier(
        criterion="gini",
        max_depth=max_depth,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=random_seed,
    )
    final_tree.fit(features, labels)
    importance = sorted(
        (
            {"feature": FEATURE_LABELS[name], "importance": float(value)}
            for name, value in zip(FEATURES, final_tree.feature_importances_, strict=True)
        ),
        key=lambda item: float(item["importance"]),
        reverse=True,
    )
    rules = export_text(final_tree, feature_names=[FEATURE_LABELS[name] for name in FEATURES], decimals=1)
    return ConsistencyTrainingResult(
        estimator=final_tree,
        metrics=metrics,
        confusion=confusion,
        feature_importance=importance,
        train_count=len(train_idx),
        test_count=len(test_idx),
        class_counts={label: int(counts.get(label, 0)) for label in RISK_LEVELS},
        parameters={
            "criterion": "gini",
            "max_depth": max_depth,
            "features": FEATURES,
            "min_samples_leaf": 3,
            "class_weight": "balanced",
            "test_size": test_size,
            "random_state": random_seed,
            "split": "GroupShuffleSplit por SKU",
            "label_source": "prioridad_revision_hu04_v2",
        },
        tree_rules=rules,
        tree_diagram=export_tree_diagram(final_tree),
    )


def explain_prediction(estimator: DecisionTreeClassifier, features: dict[str, Any]) -> str:
    """Devuelve las condiciones del recorrido del árbol que explican una predicción."""
    row = pd.DataFrame([{name: float(features[name]) for name in FEATURES}], columns=FEATURES)
    node_path = estimator.decision_path(row).indices
    explanation: list[str] = []
    for node_id in node_path[:-1]:
        feature_id = int(estimator.tree_.feature[node_id])
        threshold = float(estimator.tree_.threshold[node_id])
        feature = FEATURES[feature_id]
        value = float(features[feature])
        operator = "≤" if value <= threshold else ">"
        explanation.append(f"{FEATURE_LABELS[feature]} {operator} {threshold:g}")
    return "El árbol siguió estas condiciones: " + "; ".join(explanation) + "."


def export_tree_diagram(estimator: DecisionTreeClassifier) -> dict[str, Any]:
    """Convierte el árbol entrenado a una estructura segura para dibujarlo en la UI."""
    tree = estimator.tree_

    def build_node(node_id: int) -> dict[str, Any]:
        # Indica la clase más frecuente que alcanza el nodo y el número de observaciones.
        node_values = tree.value[node_id][0]
        prediction = str(estimator.classes_[int(node_values.argmax())])
        node: dict[str, Any] = {
            "prediction": prediction,
            "samples": int(tree.n_node_samples[node_id]),
        }
        feature_id = int(tree.feature[node_id])
        if feature_id >= 0:
            feature_name = FEATURES[feature_id]
            node.update({
                "feature": FEATURE_LABELS[feature_name],
                "threshold": round(float(tree.threshold[node_id]), 4),
                "left": build_node(int(tree.children_left[node_id])),
                "right": build_node(int(tree.children_right[node_id])),
            })
        return node

    return build_node(0)


def predict_risk(estimator: DecisionTreeClassifier, features: dict[str, Any]) -> str:
    """Aplica al perfil la misma tabla numérica usada para entrenar el árbol."""
    row = pd.DataFrame([{name: float(features[name]) for name in FEATURES}], columns=FEATURES)
    return str(estimator.predict(row)[0])
