
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    KeepTogether,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = BASE_DIR / "documents"


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(
        A4[0] / 2,
        1.2 * cm,
        f"Pagina {doc.page}"
    )
    canvas.restoreState()


def generate_pdf(source_file):
    source_path = DOCUMENTS_DIR / source_file
    output_path = source_path.with_suffix(".pdf")

    content = source_path.read_text(encoding="utf-8-sig")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="DocumentTitleCustom",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=16,
    ))

    styles.add(ParagraphStyle(
        name="SectionTitleCustom",
        parent=styles["Heading2"],
        spaceBefore=14,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=6,
    ))

    story = []
    lines = content.splitlines()

    for line in lines:
        line = line.strip()

        if not line:
            story.append(Spacer(1, 7))
            continue

        safe_line = escape(line)

        if line.startswith("# "):
            story.append(
                Paragraph(
                    safe_line[2:],
                    styles["DocumentTitleCustom"]
                )
            )

        elif line.startswith("ARTICULO ") or line.startswith("PREGUNTA "):
            story.append(
                Paragraph(
                    safe_line,
                    styles["SectionTitleCustom"]
                )
            )

        elif line in ("AVISO IMPORTANTE", "RESPUESTA:"):
            story.append(
                Paragraph(
                    f"<b>{safe_line}</b>",
                    styles["BodyCustom"]
                )
            )

        else:
            story.append(
                Paragraph(safe_line, styles["BodyCustom"])
            )

    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    print(f"PDF generado: {output_path.name}")


if __name__ == "__main__":
    generate_pdf("reglamento_academico_simulado.txt")
    generate_pdf("preguntas_frecuentes_simuladas.txt")
