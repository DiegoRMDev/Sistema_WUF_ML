"""Preparación y entrenamiento didáctico del agrupador K-Means para OE3."""

from collections import Counter
from typing import Any

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# pandas organiza filas y columnas; scikit-learn prepara variables y ejecuta K-Means.
from app.domain.disadvantaged_profiles import classify_profile

# La especie, el SKU, el nombre, la etiqueta HU02 y la salida de OE1 se excluyen
# deliberadamente: OE3 agrupa por características del perfil, sin predecir adopción.
NUMERIC_FEATURES = ["edad_meses", "edad_estimada", "tamano_estimado", "condicion_especial"]
CATEGORICAL_FEATURES = ["tamano", "nivel_energia"]
FEATURE_NAMES = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]


class ProfileClusteringError(ValueError):
    """Problema de datos o parámetros que impide crear segmentos útiles."""


def select_disadvantaged_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aplica los criterios actuales de HU06 y devuelve solo perfiles elegibles."""
    eligible = []
    for profile in profiles:
        classified = classify_profile(profile)
        if classified["es_desfavorecida"]:
            eligible.append(classified)
    return eligible


def prepare_profile_features(profiles: list[dict[str, Any]]) -> pd.DataFrame:
    """Aplica la misma selección y normalización al entrenar y asignar segmentos."""
    rows = [{name: profile.get(name) for name in FEATURE_NAMES} for profile in profiles]
    frame = pd.DataFrame(rows, columns=FEATURE_NAMES)
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].fillna("desconocido").astype(str).str.strip().str.casefold()
    return frame


def _pipeline(cluster_count: int, seed: int, n_init: int) -> Pipeline:
    """Imputa vacíos, escala números y codifica categorías antes de K-Means."""
    numeric = Pipeline([
        # La mediana evita descartar perfiles sin edad; la marca permite reconocer el vacío.
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        # La escala evita que la edad, medida en decenas de meses, domine variables binarias.
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        # K-Means necesita números: one-hot crea indicadores para cada categoría observada.
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])
    preparation = ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("preparation", preparation),
        # random_state hace reproducible el ajuste; n_init compara varias posiciones iniciales.
        ("kmeans", KMeans(n_clusters=cluster_count, random_state=seed, n_init=n_init)),
    ])


def _cluster_summary(
    profiles: list[dict[str, Any]], labels: list[int], cluster_count: int,
) -> list[dict[str, Any]]:
    """Resume cada grupo con conteos y modas legibles para el usuario."""
    summaries = []
    for cluster_id in range(cluster_count):
        members = [
            profile for profile, label in zip(profiles, labels, strict=True)
            if label == cluster_id
        ]
        if not members:
            raise ProfileClusteringError(
                "K-Means produjo un grupo vacío; prueba otro número de segmentos."
            )
        sizes = Counter(str(item.get("tamano") or "No indicado").casefold() for item in members)
        energies = Counter(str(item.get("nivel_energia") or "No indicada").casefold() for item in members)
        known_ages = [
            int(item["edad_meses"])
            for item in members
            if item.get("edad_meses") is not None
        ]
        criteria_counts = Counter(
            criterion["codigo"]
            for item in members
            for criterion in item["criterios_desfavorecidos"]
        )
        summaries.append({
            "numero_segmento": cluster_id + 1,
            "nombre": f"Segmento {cluster_id + 1}",
            "cantidad_perfiles": len(members),
            "tamano_frecuente": sizes.most_common(1)[0][0],
            "energia_frecuente": energies.most_common(1)[0][0],
            "edad_mediana_meses": (
                int(pd.Series(known_ages).median()) if known_ages else None
            ),
            "edades_estimadas": sum(bool(item.get("edad_estimada")) for item in members),
            "edades_no_indicadas": sum(item.get("edad_meses") is None for item in members),
            "criterios": {
                "edad_avanzada": criteria_counts["edad_avanzada"],
                "tamano_grande": criteria_counts["tamano_grande"],
                "condicion_especial": criteria_counts["condicion_especial"],
            },
        })
    return summaries


def train_profile_clusters(
    profiles: list[dict[str, Any]], *, cluster_count: int, seed: int, n_init: int,
) -> dict[str, Any]:
    """Silhouette describe la separación de grupos, no exactitud predictiva."""
    eligible = select_disadvantaged_profiles(profiles)
    if not 2 <= cluster_count <= 5:
        raise ProfileClusteringError("El número de segmentos debe estar entre 2 y 5.")
    if len(eligible) < max(10, cluster_count * 3):
        raise ProfileClusteringError("Se necesitan al menos 10 perfiles elegibles y 3 por segmento.")

    features = prepare_profile_features(eligible)
    distinct_rows = len(features.drop_duplicates())
    if distinct_rows < cluster_count:
        raise ProfileClusteringError("Hay menos perfiles distintos que segmentos solicitados.")

    estimator = _pipeline(cluster_count, seed, n_init)
    labels = estimator.fit_predict(features).astype(int).tolist()
    cluster_sizes = Counter(labels)
    if len(cluster_sizes) != cluster_count or min(cluster_sizes.values()) < 2:
        raise ProfileClusteringError(
            "La agrupación produjo un segmento vacío o de un solo perfil; prueba otro valor de K."
        )
    transformed = estimator.named_steps["preparation"].transform(features)
    # Silhouette mide separación y cohesión interna; no requiere etiquetas objetivo.
    silhouette = float(silhouette_score(transformed, labels))
    # silhouette no está definida si todos los puntos caen en un solo grupo.
    summaries = _cluster_summary(eligible, labels, cluster_count)
    for profile, label in zip(eligible, labels, strict=True):
        profile["numero_segmento"] = label + 1

    return {
        "estimator": estimator,
        "profiles": eligible,
        "labels": labels,
        "silhouette_score": silhouette,
        "inertia": float(estimator.named_steps["kmeans"].inertia_),
        "cluster_summaries": summaries,
        "feature_names": FEATURE_NAMES,
        "distinct_profiles": distinct_rows,
        "parameters": {"n_clusters": cluster_count, "random_state": seed, "n_init": n_init},
    }


def project_profile_clusters(
    estimator: Pipeline,
    profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Proyecta perfiles a dos dimensiones para dibujar el resultado ya aprendido."""
    eligible = select_disadvantaged_profiles(profiles)
    if len(eligible) < 3:
        raise ProfileClusteringError("No hay suficientes perfiles para mostrar el gráfico.")

    features = prepare_profile_features(eligible)
    # K-Means asigna los grupos en el espacio completo; PCA solo sirve para dibujarlos.
    transformed = estimator.named_steps["preparation"].transform(features)
    matrix = transformed.toarray() if hasattr(transformed, "toarray") else transformed
    projection = PCA(n_components=2, svd_solver="full")
    coordinates = projection.fit_transform(matrix)
    labels = estimator.predict(features).astype(int)

    return {
        "explained_variance_ratio": [float(value) for value in projection.explained_variance_ratio_],
        "points": [
            {
                "sku": str(profile.get("sku") or ""),
                "nombre": str(profile.get("nombre") or ""),
                "numero_segmento": int(label) + 1,
                "x": float(point[0]),
                "y": float(point[1]),
            }
            for profile, label, point in zip(eligible, labels, coordinates, strict=True)
        ],
    }
