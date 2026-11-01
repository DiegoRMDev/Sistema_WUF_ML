"""Genera exportaciones HU05 con secciones independientes para OE1 y OE3."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table as PdfTable, TableStyle


OE1_HEADERS = [
    "SKU", "Nombre", "Especie", "Sexo", "Edad", "Tamaño", "Condición especial",
    "Orden de publicación", "Probabilidad estimada de adopción", "Prioridad",
]
OE3_HEADERS = ["SKU", "Nombre", "Atributos desfavorecidos", "Segmento K-Means", "Resumen del segmento"]


def _age(months: int | None, estimated: bool | None) -> str:
    if months is None:
        return "No indicada"
    years, remaining = divmod(int(months), 12)
    if years:
        value = f"{years} {'año' if years == 1 else 'años'}"
        if remaining:
            value += f" {remaining} {'mes' if remaining == 1 else 'meses'}"
    else:
        value = f"{remaining} {'mes' if remaining == 1 else 'meses'}"
    return f"{value} (est.)" if estimated else value


def _condition(item: dict[str, Any]) -> str:
    return (item.get("condicion_detalle") or "Condición especial") if item["condicion_especial"] else "Ninguna"


def _excel_text(value: Any) -> str:
    """Impide que nombres o textos del CSV se interpreten como fórmulas Excel."""
    text = str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _oe1_rows(items: list[dict[str, Any]], *, excel_safe: bool = False) -> list[list[Any]]:
    as_text = _excel_text if excel_safe else str
    return [[
        as_text(item["sku"]), as_text(item["nombre"]),
        as_text(str(item["especie"]).capitalize()),
        as_text("Hembra" if str(item["sexo"]).upper() == "H" else "Macho"),
        as_text(_age(item.get("edad_meses"), item.get("edad_estimada"))),
        as_text(str(item["tamano"]).capitalize()), as_text(_condition(item)),
        int(item["orden_publicacion"]), float(item["probabilidad_adopcion"]),
        as_text(str(item["nivel_prioridad"]).capitalize()),
    ] for item in items]


def _criteria(item: dict[str, Any]) -> str:
    criteria = item.get("criterios_desfavorecidos") or []
    labels = [f"{value['nombre']}{' (est.)' if value.get('estimado') else ''}" for value in criteria]
    return ", ".join(labels) if labels else "Ninguno"


def _cluster_description(item: dict[str, Any]) -> str:
    summary = item.get("segmento_resumen") or {}
    median_age = summary.get("edad_mediana_meses")
    age_text = f"edad mediana {median_age} meses" if median_age is not None else "edad no disponible"
    disadvantaged = summary.get("perfiles_con_atributos_desfavorecidos")
    total = summary.get("cantidad_perfiles")
    share = summary.get("porcentaje_con_atributos_desfavorecidos")
    criteria_text = (
        f"{disadvantaged} de {total} con atributos desfavorecidos ({share} %)"
        if disadvantaged is not None and total else ""
    )
    return (
        f"Tamaño frecuente: {summary.get('tamano_frecuente', '—')}; "
        f"energía frecuente: {summary.get('energia_frecuente', '—')}; {age_text}"
        f"{'; ' + criteria_text if criteria_text else ''}"
    )


def _oe3_rows(items: list[dict[str, Any]], *, excel_safe: bool = False) -> list[list[str]]:
    as_text = _excel_text if excel_safe else str
    return [[
        as_text(item["sku"]), as_text(item["nombre"]), as_text(_criteria(item)),
        as_text(item.get("segmento_nombre", f"Segmento {item['numero_segmento']}")),
        as_text(_cluster_description(item)),
    ] for item in items]


def _priority_summary(items: list[dict[str, Any]]) -> str:
    counts = Counter(str(item["nivel_prioridad"]).casefold() for item in items)
    return f"Alta: {counts['alta']} · media: {counts['media']} · baja: {counts['baja']} · total: {len(items)}"


def _style_worksheet(sheet: Any, headers: list[str], rows: list[list[Any]], *, name: str, widths: list[int]) -> None:
    sheet.append(headers)
    header_row = sheet.max_row
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="465472")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    sheet.row_dimensions[header_row].height = 32
    for values in rows:
        sheet.append(values)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = f"A{header_row + 1}"
    if rows:
        last_column = get_column_letter(len(headers))
        table = Table(displayName=name, ref=f"A{header_row}:{last_column}{sheet.max_row}")
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False,
        )
        sheet.add_table(table)


def export_xlsx(report: dict[str, Any], generated_at: datetime) -> bytes:
    """Exporta OE1 y OE3 en hojas distintas para evitar mezclar sus resultados."""
    workbook = Workbook()
    oe1 = workbook.active
    oe1.title = "OE1 Priorización"
    oe3 = workbook.create_sheet("OE3 Segmentos")
    capture, model = report["captura"], report["modelo"]
    segment = report.get("oe3") or {}
    for sheet, title, model_text, total_columns in [
        (oe1, "OE1 · Priorización de difusión", f"Random Forest v{model['version']}", len(OE1_HEADERS)),
        (oe3, "OE3 · Agrupación del catálogo", f"K-Means {segment.get('modelo_version') or 'no aplicado'}", len(OE3_HEADERS)),
    ]:
        sheet.append([title])
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_columns)
        sheet["A1"].font = Font(bold=True, size=16, color="FFFFFF")
        sheet["A1"].fill = PatternFill("solid", fgColor="28344F")
        sheet["A1"].alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 28
        sheet.append([
            f"Semana ISO {capture['semana']} · Captura {capture['fecha_captura'].strftime('%d/%m/%Y')} · "
            f"{model_text} · Generado {generated_at.strftime('%d/%m/%Y %H:%M')} (Lima)"
        ])
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_columns)
        sheet["A2"].font = Font(italic=True, color="6B6F76")

    oe1.append([_priority_summary(report["items"])])
    oe1.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(OE1_HEADERS))
    oe1["A3"].font = Font(bold=True, color="28344F")
    oe1.append(["La probabilidad estimada se calcula con la etiqueta de salida del catálogo de HU02."])
    oe1.merge_cells(start_row=4, start_column=1, end_row=4, end_column=len(OE1_HEADERS))
    oe1["A4"].font = Font(italic=True, color="6B6F76")
    _style_worksheet(
        oe1, OE1_HEADERS, _oe1_rows(report["items"], excel_safe=True), name="PrioridadOE1",
        widths=[14, 24, 14, 12, 20, 14, 34, 19, 28, 14],
    )
    if report["items"]:
        for row in range(6, oe1.max_row + 1):
            oe1.cell(row, 9).number_format = "0.0%"

    silhouette = segment.get("silhouette_score")
    oe3["A3"] = (
        f"{len(segment.get('items', []))} perfiles agrupados · "
        f"{segment.get('total_desfavorecidos', 0)} con atributos desfavorecidos · silhouette: "
        f"{float(silhouette):.3f}" if silhouette is not None
        else "No hay un modelo K-Means aplicado a esta captura."
    )
    oe3.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(OE3_HEADERS))
    oe3["A3"].font = Font(bold=True, color="28344F")
    _style_worksheet(
        oe3, OE3_HEADERS, _oe3_rows(segment.get("items", []), excel_safe=True),
        name="SegmentacionOE3", widths=[14, 24, 35, 20, 62],
    )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _pdf_table(headers: list[str], rows: list[list[Any]], widths: list[float], style: ParagraphStyle) -> PdfTable:
    data = [[Paragraph(escape(header), style) for header in headers]]
    for row in rows:
        data.append([Paragraph(escape(str(value)), style) for value in row])
    table = PdfTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#28344F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DCE4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F5F7")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def export_pdf(report: dict[str, Any], generated_at: datetime) -> bytes:
    """Construye secciones y tablas separadas, cada una identificada por su objetivo."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(letter), rightMargin=0.35 * inch,
        leftMargin=0.35 * inch, topMargin=0.35 * inch, bottomMargin=0.35 * inch,
        title="Reporte de priorización y segmentación",
    )
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#28344F")
    meta = ParagraphStyle("ReportMeta", parent=styles["Normal"], fontSize=8.5, leading=12)
    cell = ParagraphStyle("ReportCell", parent=styles["Normal"], fontSize=7, leading=9, alignment=TA_LEFT)
    capture, model = report["captura"], report["modelo"]
    segment = report.get("oe3") or {}
    story = [
        Paragraph("Reporte semanal de priorización", styles["Title"]),
        Paragraph(
            f"Semana ISO {capture['semana']} · Captura {capture['fecha_captura'].strftime('%d/%m/%Y')} · "
            f"Generado {generated_at.strftime('%d/%m/%Y %H:%M')} (Lima)", meta,
        ),
        Spacer(1, 8), Paragraph(f"OE1 · Priorización de difusión · Random Forest v{escape(str(model['version']))}", styles["Heading2"]),
        Paragraph(escape(_priority_summary(report["items"])), meta),
    ]
    oe1 = _oe1_rows(report["items"])
    for row in oe1:
        row[8] = f"{float(row[8]) * 100:.1f} %"
    width = landscape(letter)[0] - 0.7 * inch
    oe1_ratios = [0.06, 0.09, 0.06, 0.05, 0.08, 0.06, 0.14, 0.08, 0.20, 0.08]
    story.append(_pdf_table(OE1_HEADERS, oe1, [width * value / sum(oe1_ratios) for value in oe1_ratios], cell))
    story.extend([PageBreak(), Paragraph("OE3 · Mascotas agrupadas por segmento", styles["Heading2"])])
    story.append(Paragraph(
        f"K-Means {escape(str(segment.get('modelo_version') or 'no aplicado'))} · "
        f"{len(segment.get('items', []))} perfiles agrupados · "
        f"{segment.get('total_desfavorecidos', 0)} con atributos desfavorecidos · "
        f"Silhouette {float(segment['silhouette_score']):.3f}" if segment.get("silhouette_score") is not None
        else "No hay un modelo K-Means aplicado a esta captura.", meta,
    ))
    story.append(Spacer(1, 8))
    story.append(_pdf_table(OE3_HEADERS, _oe3_rows(segment.get("items", [])),
                            [0.08 * width, 0.13 * width, 0.22 * width, 0.15 * width, 0.42 * width], cell))
    document.build(story)
    return output.getvalue()
