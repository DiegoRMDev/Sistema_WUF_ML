"""Genera CSV sintéticos y reproducibles para las pruebas HU02, HU03 y HU06.

El escenario conserva el flujo semanal 180→165→190. Las relaciones entre
atributos y salida del catálogo son supuestos demostrativos, no datos reales.
Esta versión regenera las etiquetas desde los atributos para que no queden
heredadas de la captura base después de modificar edad y condición.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/capturas/escenario_hu02_v3/captura_demo_2026-09-28.csv"
OUTPUT = ROOT / "data/capturas/escenario_hu02_variable_v4"
CAPTURE_DATES = ("2026-09-28", "2026-10-05", "2026-10-12")
SEED = 20261021
PUPPY_MAX_MONTHS = 11
SENIOR_MIN_MONTHS = 96

PET_NAMES = (
    "Moka", "Nala", "Bruno", "Kira", "Toby", "Canela", "Milo", "Frida",
    "Simba", "Chaska", "Pelusa", "Coco", "Mora", "Rocky", "Kiara", "Pancho",
    "Lila", "Thor", "Nina", "Rayo", "Tita", "Balú", "Pipo", "Alma", "Boni",
    "Duna", "Félix", "Gala", "Hachi", "Inti", "Jazmín", "Kiko", "Lola", "Manchitas",
    "Nube", "Oreo", "Peca", "Quilla", "Rufus", "Salem", "Tango", "Uma", "Vainilla",
    "Wasi", "Yuki", "Zuri",
)
DOG_BREEDS = ("Mestizo", "Labrador", "Schnauzer", "Terrier", "Poodle", "Pastor", "Bulldog", "Cocker")
CAT_BREEDS = ("Mestizo", "Doméstico pelo corto", "Doméstico pelo largo", "Siamés", "Persa", "Angora")


def refresh_standardized_labels(row: dict[str, str]) -> None:
    """Deriva etiquetas de edad y condición de los campos ya actualizados.

    La edad ausente no recibe una etiqueta etaria; la edad estimada con valor
    sí puede recibirla, pues `edad_estimada` conserva esa incertidumbre aparte.
    """
    labels: list[str] = []
    raw_age = row["edad_meses"].strip()
    if raw_age:
        age_months = int(raw_age)
        if age_months <= PUPPY_MAX_MONTHS:
            labels.append("Cachorro")
        elif age_months >= SENIOR_MIN_MONTHS:
            labels.append("Senior")
    if row["condicion_especial"] == "true":
        labels.append("Condicion especial")
    row["etiquetas"] = "|".join(labels)


def validate_profile_labels(row: dict[str, str]) -> None:
    """Falla al generar si las etiquetas contradicen los atributos fuente."""
    labels = [label.strip() for label in row["etiquetas"].split("|") if label.strip()]
    if len(labels) != len(set(labels)):
        raise ValueError(f"El perfil {row['sku']} contiene etiquetas duplicadas.")
    expected = dict(row)
    refresh_standardized_labels(expected)
    if labels != [label for label in expected["etiquetas"].split("|") if label]:
        raise ValueError(f"Las etiquetas del perfil {row['sku']} no concuerdan con sus atributos.")
    if not row["edad_meses"].strip() and row["edad_estimada"] != "false":
        raise ValueError(f"El perfil {row['sku']} no puede marcar edad estimada sin valor de edad.")
    if row["condicion_especial"] == "true" and not row["condicion_detalle"].strip():
        raise ValueError(f"El perfil {row['sku']} necesita detalle para su condición especial.")
    if row["condicion_especial"] == "false" and row["condicion_detalle"].strip():
        raise ValueError(f"El perfil {row['sku']} no debe tener detalle si no tiene condición especial.")


def read_capture(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Lee los encabezados y perfiles de la captura inicial."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"El archivo no tiene encabezados: {path}")
        return list(reader.fieldnames), list(reader)


def write_capture(headers: list[str], rows: list[dict[str, str]], capture_date: str) -> None:
    """Guarda la captura con su orden de publicación consecutivo."""
    output_path = OUTPUT / f"captura_demo_{capture_date}.csv"
    for position, row in enumerate(rows, start=1):
        row["orden_publicacion"] = str(len(rows) - position + 1)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def enrich_baseline(rows: list[dict[str, str]], rng: random.Random) -> None:
    """Varía atributos para romper el patrón artificial que seguía el SKU."""
    for row in rows:
        species = row["especie"]
        row["raza"] = rng.choice(DOG_BREEDS if species == "perro" else CAT_BREEDS)
        row["edad_meses"] = "" if rng.random() < 0.04 else str(rng.randint(1, 180))
        # Si no existe edad numérica, la ausencia se identifica por el valor vacío;
        # no se marca como estimada una edad que no tiene valor para estimar.
        row["edad_estimada"] = str(rng.random() < 0.30).lower() if row["edad_meses"] else "false"
        if species == "gato":
            row["tamano"] = rng.choices(("pequeno", "mediano"), weights=(0.72, 0.28))[0]
        else:
            row["tamano"] = rng.choices(("pequeno", "mediano", "grande"), weights=(0.32, 0.43, 0.25))[0]
        row["tamano_estimado"] = str(rng.random() < 0.22).lower()
        row["tipo_pelaje"] = rng.choice(("corto", "medio", "largo"))
        row["nivel_energia"] = rng.choice(("bajo", "medio", "alto"))
        row["condicion_especial"] = str(rng.random() < 0.16).lower()
        row["condicion_detalle"] = (
            rng.choice(("En tratamiento", "Movilidad reducida", "Requiere adaptación", "Condición crónica controlada"))
            if row["condicion_especial"] == "true" else ""
        )
        row["descripcion"] = (
            f"{row['nombre']} es un perfil sintético de demostración; "
            "sus atributos fueron generados para probar el historial y el modelo."
        )
        refresh_standardized_labels(row)


def adoption_proxy_score(row: dict[str, str], rng: random.Random) -> float:
    """Calcula una propensión ilustrativa con ruido para evitar una regla perfecta.

    En esta simulación, edad menor, tamaño pequeño y no tener condición especial
    elevan moderadamente la posibilidad de salir del catálogo. No son conclusiones
    causales ni se basan en resultados reales de adopción.
    """
    age = int(row["edad_meses"]) if row["edad_meses"] else 90
    age_score = max(0.0, 1.0 - age / 180)
    size_score = {"pequeno": 1.0, "mediano": 0.58, "grande": 0.16}[row["tamano"]]
    special_score = 0.0 if row["condicion_especial"] == "true" else 1.0
    # El ruido permite que perfiles con atributos semejantes tengan resultados distintos.
    return 0.50 * age_score + 0.30 * size_score + 0.20 * special_score + rng.gauss(0, 0.08)


def main() -> None:
    """Construye las tres capturas y mantiene los conteos y flujos de HU02."""
    rng = random.Random(SEED)
    headers, baseline = read_capture(SOURCE)
    by_sku = {row["sku"]: row for row in baseline}
    if len(baseline) != 180 or len(by_sku) != len(baseline):
        raise ValueError("La captura base debe contener 180 perfiles con SKU únicos.")

    enrich_baseline(baseline, rng)
    # Rompe el orden heredado del CSV fuente antes de asignar posición de catálogo.
    rng.shuffle(baseline)
    available = [row for row in baseline if row["estado_publicado"] == "disponible"]
    initially_unavailable = [row for row in baseline if row["estado_publicado"] == "no_disponible"]
    if len(available) != 108 or len(initially_unavailable) != 72:
        raise ValueError("La captura base esperada contiene 108 disponibles y 72 no disponibles.")

    # Ordenamos por una señal sintética ruidosa, nunca por SKU u orden de publicación.
    ranked = sorted(available, key=lambda row: adoption_proxy_score(row, rng), reverse=True)
    early_exit = {row["sku"] for row in ranked[:10]}
    exit_after_two = {row["sku"] for row in ranked[10:21]}
    late_exit = {row["sku"] for row in ranked[21:42]}

    OUTPUT.mkdir(parents=True, exist_ok=True)
    week_40 = [dict(row) for row in baseline]
    write_capture(headers, week_40, CAPTURE_DATES[0])

    # 15 mascotas ya no disponibles salen del catálogo; 21 de la cohorte cambian de estado.
    absent_old = {row["sku"] for row in initially_unavailable[:15]}
    week_41 = [dict(row) for row in baseline if row["sku"] not in absent_old]
    for row in week_41:
        if row["sku"] in early_exit | exit_after_two:
            row["estado_publicado"] = "no_disponible"
    if len(week_41) != 165:
        raise ValueError("La segunda captura debe contener 165 perfiles.")
    write_capture(headers, week_41, CAPTURE_DATES[1])

    # Diez salidas desaparecen tras una semana no disponibles; 21 cambian en la última.
    week_42 = [dict(row) for row in week_41 if row["sku"] not in early_exit]
    for row in week_42:
        if row["sku"] in late_exit:
            row["estado_publicado"] = "no_disponible"

    # Las altas reciben nombres y combinaciones de atributos plausibles, sin etiquetas genéricas.
    names = list(PET_NAMES)
    rng.shuffle(names)
    for offset in range(35):
        sku = f"WUF{181 + offset:04d}"
        species = rng.choice(("perro", "perro", "gato"))
        age = rng.randint(2, 180)
        size = rng.choice(("pequeno", "mediano")) if species == "gato" else rng.choice(("pequeno", "mediano", "grande"))
        special = rng.random() < 0.16
        profile = {
            "sku": sku,
            "nombre": names[offset],
            "especie": species,
            "raza": rng.choice(DOG_BREEDS if species == "perro" else CAT_BREEDS),
            "sexo": rng.choice(("M", "H")),
            "edad_meses": str(age),
            "edad_estimada": str(rng.random() < 0.30).lower(),
            "tipo_pelaje": rng.choice(("corto", "medio", "largo")),
            "tamano": size,
            "tamano_estimado": str(rng.random() < 0.22).lower(),
            "nivel_energia": rng.choice(("bajo", "medio", "alto")),
            "condicion_especial": str(special).lower(),
            "condicion_detalle": rng.choice(("En tratamiento", "Requiere adaptación")) if special else "",
            "descripcion": f"{names[offset]} es parte de un perfil sintético de demostración.",
            "orden_publicacion": "1",
            "estado_publicado": "disponible" if offset < 20 else "no_disponible",
            "fecha_publicacion": (date.fromisoformat(CAPTURE_DATES[1]) + timedelta(days=offset % 7)).isoformat(),
            "url_perfil": f"https://www.wuf.pe/adopta/{species}/{sku.lower()}",
            "etiquetas": "",
        }
        refresh_standardized_labels(profile)
        week_42.append(profile)
    if len(week_42) != 190:
        raise ValueError("La tercera captura debe contener 190 perfiles.")

    # Valida cantidades y flujos antes de sobrescribir los CSV que se importan en HU01.
    final_by_sku = {row["sku"]: row["estado_publicado"] for row in week_42}
    week_41_by_sku = {row["sku"]: row["estado_publicado"] for row in week_41}
    if (
        len(early_exit) != 10 or len(exit_after_two) != 11 or len(late_exit) != 21
        or len(early_exit | exit_after_two | late_exit) != 42
        or any(sku in final_by_sku for sku in early_exit)
        or any(week_41_by_sku[sku] != "no_disponible" or final_by_sku[sku] != "no_disponible" for sku in exit_after_two)
        or any(week_41_by_sku[sku] != "disponible" or final_by_sku[sku] != "no_disponible" for sku in late_exit)
    ):
        raise ValueError("Las transiciones de la cohorte no coinciden con el escenario documentado.")
    available_counts = [
        sum(row["estado_publicado"] == "disponible" for row in capture)
        for capture in (week_40, week_41, week_42)
    ]
    if available_counts != [108, 87, 86]:
        raise ValueError("El conteo de perfiles disponibles no coincide con el escenario documentado.")
    for capture in (week_40, week_41, week_42):
        for row in capture:
            validate_profile_labels(row)
    write_capture(headers, week_42, CAPTURE_DATES[2])

    # Comprueba que las transiciones previstas continúan sin desapariciones abruptas.
    states = [{row["sku"]: row["estado_publicado"] for row in capture} for capture in (week_40, week_41, week_42)]
    if any(states[0][sku] != "disponible" or states[1][sku] != "no_disponible" for sku in early_exit):
        raise ValueError("Flujo inesperado para las salidas tempranas.")
    print("28/09/2026: 180 perfiles, 108 disponibles, 72 no disponibles")
    print("05/10/2026: 165 perfiles, 87 disponibles, 78 no disponibles")
    print("12/10/2026: 190 perfiles, 86 disponibles, 104 no disponibles")
    print("Cohorte HU02: 66 permanecen y 42 salen del catálogo (10 + 11 + 21).")


if __name__ == "__main__":
    main()
