
"""Reglas de autorización para UniTramite AI.

Las identidades utilizadas en las pruebas son simuladas.
Este módulo no implementa autenticación.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    student_id: str | None = None
    role: str = "anonymous"


def can_view_request(identity, request):
    """Comprueba si una identidad puede consultar una solicitud."""
    if identity is None or request is None:
        return False

    if identity.role == "admin":
        return True

    if identity.role == "student":
        return (
            bool(identity.student_id)
            and identity.student_id == request.get("student_id")
        )

    return False


def can_manage_requests(identity):
    """Solo los administradores pueden gestionar solicitudes."""
    return identity is not None and identity.role == "admin"


def can_manage_students(identity):
    """Solo los administradores pueden gestionar estudiantes."""
    return identity is not None and identity.role == "admin"


def can_manage_documents(identity):
    """Solo los administradores pueden gestionar documentos."""
    return identity is not None and identity.role == "admin"
