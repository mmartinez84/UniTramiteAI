
import re

from core import handle_message, faq_answer
from ai_chatbot import answer_with_ai


def is_informational_question(prompt):
    """
    Detecta preguntas informativas explícitas.
    No ejecuta operaciones administrativas.
    """
    text = prompt.strip().lower()

    informational_starts = (
        "qué ",
        "que ",
        "cuáles ",
        "cuales ",
        "cómo ",
        "como ",
        "por qué ",
        "porque ",
        "para qué ",
        "para que ",
        "cuánto ",
        "cuanto ",
        "dónde ",
        "donde ",
    )

    return (
        text.startswith("¿")
        or text.startswith(informational_starts)
    )


def route_message(prompt, state):
    """
    Dirige las consultas al mecanismo correspondiente.
    Las operaciones siguen bajo control de core.py.
    """

    # Si existe un trámite pendiente, conservar su flujo.
    if state.get("pending_type") or state.get("pending_student"):
        return handle_message(prompt, state)

    # Los identificadores de tickets y matrículas
    # deben procesarse mediante las reglas tradicionales.
    if re.search(r"UT-\d{6}", prompt.upper()):
        return handle_message(prompt, state)

    if re.search(r"\b\d{4}-\d{4}\b", prompt):
        return handle_message(prompt, state)

    # Consultas informativas explícitas.
    if is_informational_question(prompt):
        response = answer_with_ai(prompt)

        if response:
            return response

        return (
            "En este momento no puedo completar la consulta "
            "documental. Inténtalo nuevamente más tarde. "
            "Los procedimientos de UniTramite AI son simulados."
        )

    # Operaciones y mensajes restantes.
    return handle_message(prompt, state)
