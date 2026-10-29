
import re

from rag.pdf_loader import load_all_pdfs


def split_text(text, chunk_size=700, overlap=120):
    """
    Divide el texto en fragmentos con solapamiento,
    procurando respetar los límites de palabras.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que cero")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap debe estar entre 0 y chunk_size - 1")

    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            last_space = text.rfind(" ", start, end + 1)

            if last_space > start:
                end = last_space

        chunk = text[start:end].strip()

        if chunk:
            chunks.append((start, end, chunk))

        if end >= len(text):
            break

        next_start = max(0, end - overlap)

        # Avanzar hasta el inicio de una palabra.
        if next_start > 0 and not text[next_start - 1].isspace():
            while next_start < end and not text[next_start].isspace():
                next_start += 1

            while next_start < end and text[next_start].isspace():
                next_start += 1

        if next_start <= start or next_start >= end:
            next_start = end

        start = next_start

    return chunks



def create_chunks(pages, chunk_size=700, overlap=120):
    """
    Crea fragmentos por artículo o pregunta,
    conservando las páginas de origen.
    """
    documents = {}

    for page in pages:
        documents.setdefault(page["source"], []).append(page)

    all_chunks = []

    for source, document_pages in documents.items():
        document_pages.sort(key=lambda item: item["page"])

        full_text = ""
        page_ranges = []

        for page in document_pages:
            page_text = re.sub(
                r"^Pagina\s+\d+\s*",
                "",
                page["text"].strip(),
                count=1,
            )

            normalized = " ".join(page_text.split())

            if not normalized:
                continue

            if full_text:
                full_text += " "

            start = len(full_text)
            full_text += normalized
            end = len(full_text)

            page_ranges.append((start, end, page["page"]))

        # Detectar los comienzos de artículos o preguntas.
        pattern = r"\b(?:ARTICULO|PREGUNTA)\s+\d+\."

        matches = list(re.finditer(pattern, full_text))

        sections = []

        if matches:
            for index, match in enumerate(matches):
                section_start = match.start()

                section_end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(full_text)
                )

                sections.append((
                    section_start,
                    section_end,
                    full_text[section_start:section_end].strip(),
                ))

        else:
            sections.append((0, len(full_text), full_text))

        for index, (start, end, section_text) in enumerate(
            sections, start=1
        ):
            if not section_text:
                continue

            pages_in_section = [
                page_number
                for page_start, page_end, page_number in page_ranges
                if start < page_end and end > page_start
            ]

            if not pages_in_section:
                continue

            all_chunks.append({
                "id": f"{source}-s{index}",
                "source": source,
                "page_start": min(pages_in_section),
                "page_end": max(pages_in_section),
                "text": section_text,
            })

    return all_chunks



if __name__ == "__main__":
    pages = load_all_pdfs()
    chunks = create_chunks(pages)

    print(f"Total de páginas: {len(pages)}")
    print(f"Total de fragmentos: {len(chunks)}")

    for chunk in chunks:
        print("-" * 60)
        print(f"ID: {chunk['id']}")
        print(f"Fuente: {chunk['source']}")
        print(
            f"Páginas: {chunk['page_start']} "
            f"a {chunk['page_end']}"
        )
        print(f"Caracteres: {len(chunk['text'])}")
        print(f"Texto: {chunk['text'][:150]}...")
