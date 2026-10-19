"""Reglas puras para construir las etiquetas de HU02 a partir de snapshots."""

from collections.abc import Sequence
from datetime import date


def validate_followup_period(start_date: date, end_date: date, capture_count: int) -> int:
    """Requiere tres capturas en un horizonte de semanas completas y devuelve semanas."""
    if capture_count < 3:
        raise ValueError("El periodo debe incluir al menos tres capturas completas para el seguimiento.")
    days = (end_date - start_date).days
    if days < 14 or days % 7:
        raise ValueError("El horizonte debe abarcar al menos dos semanas completas.")
    return days // 7


def classify_cohort_pet(states: Sequence[str | None]) -> tuple[str, str | None, int | None]:
    """Clasifica una mascota que estaba disponible en la captura de referencia.

    ``states`` incluye una posición por ejecución completa, en orden cronológico.
    Un estado ausente representa que la mascota no apareció en esa ejecución.
    """
    if not states or states[0] != "disponible":
        raise ValueError("La cohorte solo puede incluir mascotas disponibles en la referencia.")

    has_ambiguous_state = False
    for index, state in enumerate(states[1:], start=1):
        if state == "no_disponible" or state is None:
            reason = "estado_no_disponible" if state == "no_disponible" else "ausencia_en_captura_completa"
            return "salio_catalogo", reason, index
        if state != "disponible":
            has_ambiguous_state = True

    if has_ambiguous_state:
        return "indeterminada", "estado_sin_evidencia_concluyente", None

    if len(states) < 2:
        return "indeterminada", "sin_captura_posterior", None
    return "permanece", None, len(states) - 1
