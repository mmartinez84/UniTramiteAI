
import os

from openai import OpenAI


SYSTEM_INSTRUCTIONS = """
Eres el asistente virtual de UniTramite AI, un prototipo
académico de atención a estudiantes universitarios.

Tu función es orientar a los estudiantes sobre trámites
académicos y responder preguntas generales.

Reglas:
- Responde siempre en español, de forma clara y amable.
- No inventes requisitos, costos, plazos ni políticas.
- Aclara que los datos y procesos del prototipo son simulados.
- No afirmes que tienes acceso a sistemas universitarios reales.
- No afirmes que has registrado o aprobado solicitudes.
- No solicites contraseñas ni información personal sensible.
- Para consultar un ticket o registrar una solicitud, indica
  que esas operaciones se gestionan mediante UniTramite AI.
- Si desconoces una política oficial, recomienda confirmarla
  con la universidad.
"""


def get_api_key():
    """Obtiene la clave sin mostrarla ni guardarla en el código."""
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key

    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY")
    except (FileNotFoundError, KeyError):
        return None


def answer_with_ai(question):
    """
    Responde consultas generales.
    Devuelve None si no hay clave o si falla la API.
    """
    try:
        import streamlit as st
        ai_enabled = st.secrets.get("OPENAI_ENABLED", False)
    except (FileNotFoundError, KeyError):
        ai_enabled = False

    if not ai_enabled:
        return None
    api_key = get_api_key()

    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key, timeout=15.0)

        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions=SYSTEM_INSTRUCTIONS,
            input=question,
            max_output_tokens=300,
        )

        return response.output_text.strip() or None

    except Exception:
        # Permite que el chatbot use su respuesta tradicional.
        return None
