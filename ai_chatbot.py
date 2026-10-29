
import os

from openai import OpenAI

from rag.rag_pipeline import build_rag_messages


GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Modelo configurable para evitar depender de un
# identificador fijo que pueda quedar obsoleto.
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def get_setting(name, default=None):
    """
    Lee configuraciones desde variables de entorno
    o desde Streamlit Secrets.
    """
    value = os.getenv(name)

    if value is not None:
        return value

    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default


def is_ai_enabled():
    """
    Comprueba si la integración está habilitada.
    """
    value = get_setting("AI_ENABLED", False)

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in (
        "true", "1", "yes", "on"
    )


def answer_with_ai(question):
    """
    Responde preguntas informativas utilizando
    GroqCloud y el contexto documental RAG.

    Devuelve None cuando:
    - La IA está deshabilitada.
    - No hay información documental relevante.
    - No existe clave API.
    - La solicitud al proveedor falla.
    """
    if not is_ai_enabled():
        return None

    provider = str(
        get_setting("AI_PROVIDER", "groq")
    ).strip().lower()

    if provider != "groq":
        return None

    rag_result = build_rag_messages(question)

    if rag_result is None:
        return (
            "No dispongo de información suficiente en los "
            "documentos académicos simulados de UniTramite AI "
            "para responder esta pregunta. Te recomiendo "
            "consultar directamente con la universidad para "
            "obtener información oficial."
        )

    api_key = get_setting("GROQ_API_KEY")

    if not api_key:
        return None

    model = get_setting(
        "GROQ_MODEL",
        DEFAULT_GROQ_MODEL,
    )

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL,
            timeout=20.0,
            max_retries=0,
        )

        response = client.chat.completions.create(
            model=model,
            messages=rag_result["messages"],
            temperature=0,
            max_tokens=400,
        )

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            return None

        return answer.strip()

    except Exception as error:
        print(
            "[GroqCloud] Error durante la generación:",
            type(error).__name__,
        )
        return None


if __name__ == "__main__":
    questions = [
        "¿Hasta cuándo puedo retirar una asignatura?",
        "¿Cuánto tarda una certificación académica?",
        "¿Cuál es el horario de la biblioteca?",
    ]

    for question in questions:
        print("=" * 65)
        print(f"PREGUNTA: {question}")

        answer = answer_with_ai(question)

        if answer is None:
            print("Sin respuesta de IA.")
        else:
            print(f"RESPUESTA:\n{answer}")

