"""Reglas HU06 para identificar atributos asociados a perfiles desfavorecidos."""

from collections import Counter
from typing import Any


# Ocho años es el umbral acordado para este escenario de demostración.
SENIOR_AGE_MONTHS = 96

CRITERIA = {
    "edad_avanzada": "Edad avanzada",
    "tamano_grande": "Tamaño grande",
    "condicion_especial": "Condición especial",
}


def classify_profile(item: dict[str, Any]) -> dict[str, Any]:
    """Anota los criterios cumplidos; los valores desconocidos no cuentan como falsos."""
    criteria: list[dict[str, str | bool]] = []
    age_months = item.get("edad_meses")

    # Una edad estimada puede calificar, pero se marca para que el equipo la interprete.
    if age_months is not None and int(age_months) >= SENIOR_AGE_MONTHS:
        criteria.append({
            "codigo": "edad_avanzada",
            "nombre": CRITERIA["edad_avanzada"],
            "estimado": bool(item.get("edad_estimada")),
        })

    # El tamaño sigue el mismo criterio: se incluye si está estimado y se indica como tal.
    if str(item.get("tamano", "")).strip().casefold() == "grande":
        criteria.append({
            "codigo": "tamano_grande",
            "nombre": CRITERIA["tamano_grande"],
            "estimado": bool(item.get("tamano_estimado")),
        })

    if bool(item.get("condicion_especial")):
        criteria.append({
            "codigo": "condicion_especial",
            "nombre": CRITERIA["condicion_especial"],
            "estimado": False,
        })

    return {
        **item,
        "criterios_desfavorecidos": criteria,
        "es_desfavorecida": bool(criteria),
        "edad_desconocida": age_months is None,
    }


def summarize_profiles(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Cuenta criterios que pueden superponerse y perfiles únicos del segmento."""
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(criterion["codigo"] for criterion in item["criterios_desfavorecidos"])

    return {
        "total_desfavorecidas": sum(item["es_desfavorecida"] for item in items),
        "por_criterio": {code: counts[code] for code in CRITERIA},
        "edades_no_indicadas": sum(item["edad_desconocida"] for item in items),
    }

