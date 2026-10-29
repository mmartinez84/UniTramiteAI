
from pathlib import Path

import pymupdf


BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = BASE_DIR / "documents"


def load_pdf(pdf_path):
    """
    Extrae el texto de un PDF página por página.

    Devuelve una lista de diccionarios con:
    - source: nombre del documento
    - page: número de página
    - text: contenido extraído
    """
    pdf_path = Path(pdf_path)
    pages = []

    with pymupdf.open(str(pdf_path)) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()

            if not text:
                continue

            pages.append({
                "source": pdf_path.name,
                "page": page_number,
                "text": text,
            })

    return pages


def load_all_pdfs():
    """
    Carga todos los PDF de la carpeta documents.
    """
    all_pages = []

    for pdf_path in sorted(DOCUMENTS_DIR.glob("*.pdf")):
        all_pages.extend(load_pdf(pdf_path))

    return all_pages


if __name__ == "__main__":
    pages = load_all_pdfs()

    print(f"Total de páginas con texto: {len(pages)}")

    for page in pages:
        print("-" * 60)
        print(f"Documento: {page['source']}")
        print(f"Página: {page['page']}")
        print(f"Caracteres extraídos: {len(page['text'])}")
        print(f"Vista previa: {page['text'][:200]}")
