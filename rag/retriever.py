
from functools import lru_cache
import unicodedata
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rag.pdf_loader import load_all_pdfs
from rag.text_chunker import create_chunks



def normalize_text(text):
    """
    Normaliza acentos y expresiones académicas
    equivalentes para mejorar la recuperación TF-IDF.
    """
    text = text.lower()

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    # Unificar términos académicos equivalentes.
    synonyms = [
        (r"\bmaterias?\b", "asignatura"),
        (r"\bdar de baja\b", "retirar"),
        (r"\bdarme de baja de\b", "retirar"),
        (r"\bcancelar una asignatura\b", "retirar una asignatura"),
        (r"\bcancelar asignatura\b", "retirar asignatura"),
        (r"\bcancelacion de una asignatura\b", "retiro de una asignatura"),
        (r"\bcancelacion de asignatura\b", "retiro de asignatura"),
        (r"\bla fecha limite\b", "el plazo"),
        (r"\bfecha limite\b", "plazo"),
        (r"\bconstancia de estudios\b", "certificacion academica"),
        (r"\bcertificado de estudios\b", "certificacion academica"),
    ]

    for pattern, replacement in synonyms:
        text = re.sub(pattern, replacement, text)

    return text



@lru_cache(maxsize=1)
def build_retriever():
    """
    Carga los PDF, genera los fragmentos
    y construye la matriz TF-IDF.
    """
    pages = load_all_pdfs()
    chunks = create_chunks(pages)

    if not chunks:
        return [], None, None

    
    spanish_stopwords = [
        "a", "al", "ante", "bajo", "con", "contra",
        "de", "del", "desde", "durante", "e", "el",
        "ella", "en", "entre", "es", "esa", "ese",
        "esta", "este", "esto", "hay", "la", "las",
        "lo", "los", "me", "mi", "mis", "no", "o",
        "para", "pero", "por", "que", "se", "si",
        "sin", "sobre", "su", "sus", "te", "tu",
        "tus", "un", "una", "uno", "unos", "unas",
        "y", "ya", "como", "cual", "cuales",
        "cuando", "donde", "cuanto", "cuantos",
        "puedo", "puede", "debo", "debe"
    ]

    vectorizer = TfidfVectorizer(
        preprocessor=normalize_text,
        stop_words=spanish_stopwords,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )


    texts = [chunk["text"] for chunk in chunks]
    matrix = vectorizer.fit_transform(texts)

    return chunks, vectorizer, matrix

def has_thematic_match(question_vector, document_vector, vectorizer):
    """
    Comprueba que la pregunta y el documento compartan
    al menos un término temático relevante.
    """

    generic_terms = {
        "cuesta",
        "costo",
        "precio",
        "necesito",
        "solicitar",
        "solicitud",
        "documentos",
        "documento",
        "universitario",
        "universidad",
        "informacion",
        "tramite",
        "hacer",
        "obtener",
        "saber",
    }

    features = vectorizer.get_feature_names_out()

    question_terms = {
        features[index]
        for index in question_vector.indices
    }

    document_terms = {
        features[index]
        for index in document_vector.indices
    }

    shared_terms = question_terms & document_terms

    thematic_terms = {
        term
        for term in shared_terms
        if term not in generic_terms
    }

    return bool(thematic_terms)

def retrieve(question, top_k=3, min_score=0.05):
    """
    Recupera los fragmentos más relevantes.

    Devuelve una lista de diccionarios con:
    - id
    - source
    - page_start
    - page_end
    - text
    - score
    """
    if not question or not question.strip():
        return []

    if top_k <= 0:
        return []

    chunks, vectorizer, matrix = build_retriever()

    if not chunks:
        return []

    question_vector = vectorizer.transform([question])

    scores = cosine_similarity(
        question_vector,
        matrix,
    ).flatten()

    ranked_indices = scores.argsort()[::-1]

    results = []

    for index in ranked_indices:
        score = float(scores[index])

        if score < min_score:
            continue

        if not has_thematic_match(
            question_vector,
            matrix[index],
            vectorizer
        ):
            continue

        results.append({
            **chunks[index],
            "score": round(score, 4)
        })

        if len(results) >= top_k:
            break

    return results


if __name__ == "__main__":
    questions = [
        "¿Hasta cuándo puedo retirar una asignatura?",
        "¿Cuánto tarda una certificación académica?",
        "¿Qué necesito para cambiar de carrera?",
        "¿Cuánto cuesta una certificación?",
        "¿Cuál es el horario de la biblioteca?",
    ]

    for question in questions:
        print("=" * 65)
        print(f"PREGUNTA: {question}")

        results = retrieve(question)

        if not results:
            print("No se encontraron fragmentos relevantes.")
            continue

        for result in results:
            print("-" * 65)
            print(f"Fuente: {result['source']}")
            print(
                f"Páginas: {result['page_start']} "
                f"a {result['page_end']}"
            )
            print(f"Similitud: {result['score']:.4f}")
            print(f"Texto: {result['text'][:250]}...")
