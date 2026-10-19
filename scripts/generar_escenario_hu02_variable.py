"""Genera de forma reproducible tres CSV sintéticos para probar HU02.

El escenario parte de la captura estable de 180 perfiles y simula altas,
salidas por ausencia y cambios explícitos de estado entre semanas.
No consulta WUF ni modifica los CSV usados en las pruebas anteriores.
"""

import csv
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/capturas/escenario_hu02_v3/captura_demo_2026-09-28.csv"
OUTPUT = ROOT / "data/capturas/escenario_hu02_variable_v3"
CAPTURE_DATES = ("2026-09-28", "2026-10-05", "2026-10-12")


def read_capture(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Lee el CSV base conservando el orden original de columnas."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"El archivo no tiene encabezados: {path}")
        return list(reader.fieldnames), list(reader)


def write_capture(headers: list[str], rows: list[dict[str, str]], capture_date: str) -> None:
    """Escribe una captura completa con nombre/fecha aceptados por HU01."""
    output_path = OUTPUT / f"captura_demo_{capture_date}.csv"
    # El orden de publicación representa la posición visible de cada perfil.
    for position, row in enumerate(rows, start=1):
        row["orden_publicacion"] = str(len(rows) - position + 1)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Construye el caso 180→165→190 con cambios deterministas y documentados."""
    headers, baseline = read_capture(SOURCE)
    by_sku = {row["sku"]: row for row in baseline}
    if len(baseline) != 180 or len(by_sku) != len(baseline):
        raise ValueError("La captura base debe contener 180 perfiles con SKU únicos.")

    available_skus = [row["sku"] for row in baseline if row["estado_publicado"] == "disponible"]
    if len(available_skus) != 108:
        raise ValueError("La captura base esperada contiene 108 perfiles disponibles.")

    # Semana 40: referencia íntegra, sin cambios frente al catálogo base.
    week_43 = [dict(row) for row in baseline]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_capture(headers, week_43, CAPTURE_DATES[0])

    # Semana 41: 15 perfiles que ya estaban no disponibles dejan de aparecer.
    # Las 42 mascotas disponibles que saldrán del catálogo pasan primero a
    # no_disponible, así no desaparecen directamente desde disponible.
    initially_unavailable = [
        row["sku"] for row in baseline if row["estado_publicado"] == "no_disponible"
    ]
    absent_before_followup = set(initially_unavailable[:15])
    state_change_skus = set(available_skus[:21])
    week_44 = [
        dict(row) for row in baseline
        if row["sku"] not in absent_before_followup
    ]
    for row in week_44:
        if row["sku"] in state_change_skus:
            row["estado_publicado"] = "no_disponible"
    if len(week_44) != 165:
        raise ValueError("La segunda captura debe contener 165 perfiles.")
    write_capture(headers, week_44, CAPTURE_DATES[1])

    # Semana 42: 10 mascotas desaparecen luego de una semana no disponibles;
    # 11 siguen no_disponible y otras 21 pasan a no_disponible recién ahora.
    # Las 66 mascotas restantes siguen disponibles.
    disappearing_skus = set(available_skus[:10])
    week_45 = [dict(row) for row in week_44 if row["sku"] not in disappearing_skus]
    final_state_change_skus = set(available_skus[21:42])
    for row in week_45:
        if row["sku"] in final_state_change_skus:
            row["estado_publicado"] = "no_disponible"

    new_profiles: list[dict[str, str]] = []
    for offset in range(35):
        new_sku = f"WUF{181 + offset:04d}"
        # Se copian atributos válidos de perfiles demo y se identifican como altas sintéticas.
        profile = dict(baseline[offset])
        profile.update({
            "sku": new_sku,
            "nombre": f"Mascota demo {181 + offset}",
            "descripcion": "Perfil sintético de demostración incorporado en la semana 42; no corresponde a una ficha real de WUF.",
            "fecha_publicacion": (date.fromisoformat(CAPTURE_DATES[1]) + timedelta(days=offset % 7)).isoformat(),
            "url_perfil": f"https://www.wuf.pe/adopta/{profile['especie']}/{new_sku.lower()}",
            "estado_publicado": "disponible" if offset < 20 else "no_disponible",
        })
        new_profiles.append(profile)
    week_45.extend(new_profiles)
    if len(week_45) != 190:
        raise ValueError("La tercera captura debe contener 190 perfiles.")
    write_capture(headers, week_45, CAPTURE_DATES[2])

    counts = [
        (capture_date, len(rows), sum(row["estado_publicado"] == "disponible" for row in rows),
         sum(row["estado_publicado"] == "no_disponible" for row in rows))
        for capture_date, rows in zip(CAPTURE_DATES, (week_43, week_44, week_45), strict=True)
    ]
    for item in counts:
        print(f"{item[0]}: {item[1]} perfiles, {item[2]} disponibles, {item[3]} no disponibles")


if __name__ == "__main__":
    main()
