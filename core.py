import os
import sqlite3
from pathlib import Path
from datetime import datetime
from security import can_view_request, can_manage_requests, can_manage_students, can_manage_documents
import json
import re
import uuid


ROOT = Path(__file__).parent
DB_PATH = ROOT / "unitramite.db"
SEED_PATH = ROOT / "data" / "students.json"
SEED_REQUEST = ("UT-000001", "2024-1001", "Récord académico", "En proceso", "2026-10-01 09:30", "Solicitud de demostración.")

def database_url():
    """PostgreSQL URL (Neon, Supabase...). Without it, the local SQLite file is used."""
    return os.getenv("DATABASE_URL")

def connect():
    if database_url():
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(database_url(), row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def run(sql, params=(), fetch=None):
    """Run one statement on the active database; `?` placeholders work on both engines."""
    if database_url():
        sql = sql.replace("?", "%s")
    con = connect()
    try:
        with con:
            cur = con.execute(sql, params)
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()

def init_db():
    run("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            matricula_activa BOOLEAN NOT NULL,
            paz_y_salvo BOOLEAN NOT NULL,
            notes TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
    run("""
        CREATE TABLE IF NOT EXISTS requests (
            ticket TEXT PRIMARY KEY,
            student_id TEXT NOT NULL REFERENCES students(student_id),
            request_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            notes TEXT NOT NULL
        )""")

    run("""
        CREATE TABLE IF NOT EXISTS ticket_history (
            id INTEGER PRIMARY KEY,
            ticket TEXT NOT NULL REFERENCES requests(ticket),
            previous_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            observation TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")


    run("""
        CREATE TABLE IF NOT EXISTS requirements (
            id TEXT PRIMARY KEY,
            request_type TEXT NOT NULL,
            requirement_code TEXT NOT NULL,
            description TEXT NOT NULL,
            is_mandatory BOOLEAN NOT NULL,
            UNIQUE (request_type, requirement_code)
        )
    """)

    run("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            ticket TEXT NOT NULL REFERENCES requests(ticket),
            requirement_code TEXT NOT NULL,
            file_name TEXT NOT NULL,
            status TEXT NOT NULL,
            observations TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    seed_requirements()

    if database_url():
        # The sequence hands out ticket numbers atomically across concurrent users
        run("CREATE SEQUENCE IF NOT EXISTS request_number_seq START 2")
        # Supabase publishes the public schema through its REST API; RLS without
        # policies blocks that API while this app (table owner) keeps full access
        run("ALTER TABLE students ENABLE ROW LEVEL SECURITY")
        run("ALTER TABLE requests ENABLE ROW LEVEL SECURITY")
    # Seed demo students and tickets only once
    if run("SELECT COUNT(*) AS n FROM students", fetch="one")["n"] == 0:
        with open(SEED_PATH, encoding="utf-8") as f:
            for student_id, s in json.load(f).items():
                _insert_student(student_id, s["nombre"], s["matricula_activa"], s["paz_y_salvo"], s["nota"])
    if run("SELECT COUNT(*) AS n FROM requests", fetch="one")["n"] == 0:
        run("INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?)", SEED_REQUEST)

def validate_student_id_format(student_id):
    return bool(re.fullmatch(r"\d{4}-\d{4}", student_id or ""))

def _get_student(student_id):
    """Consulta interna de datos estudiantiles."""
    row = run(
        "SELECT * FROM students WHERE student_id = ?",
        (student_id,),
        fetch="one",
    )

    if row:
        row["matricula_activa"] = bool(row["matricula_activa"])
        row["paz_y_salvo"] = bool(row["paz_y_salvo"])

    return row


def get_student(student_id, *, identity=None):
    """Consulta datos estudiantiles únicamente con autorización."""

    if identity is None:
        return None

    if identity.role != "admin":
        if (
            identity.role != "student"
            or identity.student_id != student_id
        ):
            return None

    return _get_student(student_id)

def demo_student_exists(student_id):
    """Verifica una matrícula ficticia en modo demostración.

    No devuelve datos personales ni concede permisos.
    """
    import os

    if os.getenv("UNITRAMITE_DEMO_MODE", "false").lower() != "true":
        return False

    if not isinstance(student_id, str):
        return False

    import re

    if not re.fullmatch(r"\d{4}-\d{4}", student_id):
        return False

    row = run(
        "SELECT 1 FROM students WHERE student_id = ?",
        (student_id,),
        fetch="one",
    )

    return row is not None

def _insert_student(student_id, full_name, matricula_activa, paz_y_salvo, notes=""):
    """Store a new student; returns an error message, or None when it was saved."""
    student_id = (student_id or "").strip()
    full_name = (full_name or "").strip()
    if not validate_student_id_format(student_id):
        return "La matrícula debe tener el formato 0000-0000."
    if not full_name:
        return "El nombre es obligatorio."
    if _get_student(student_id):
        return f"La matrícula {student_id} ya está registrada."
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    run("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)",
        (student_id, full_name, bool(matricula_activa), bool(paz_y_salvo), notes.strip(), now))
    return None


def register_student(
    student_id,
    full_name,
    matricula_activa,
    paz_y_salvo,
    notes="",
    *,
    identity=None,
):
    """Registra estudiantes únicamente con autorización administrativa."""

    if not can_manage_students(identity):
        return (
            "Acceso denegado. Solo el personal administrativo "
            "autorizado puede registrar estudiantes."
        )

    return _insert_student(
        student_id,
        full_name,
        matricula_activa,
        paz_y_salvo,
        notes,
    )


def list_students(*, identity=None):
    """Lista estudiantes únicamente para administradores autorizados."""

    if not can_manage_students(identity):
        return []

    rows = run("""
        SELECT student_id AS "Matrícula", full_name AS "Nombre",
               matricula_activa AS "Matrícula activa", paz_y_salvo AS "Paz y salvo",
               notes AS "Nota", created_at AS "Registrado"
        FROM students ORDER BY student_id
    """, fetch="all")

    for r in rows:
        r["Matrícula activa"] = bool(r["Matrícula activa"])
        r["Paz y salvo"] = bool(r["Paz y salvo"])

    return rows


def get_requirements(request_type):
    return {
        "Récord académico": ["matricula_activa", "paz_y_salvo"],
        "Certificación de estudio": ["matricula_activa"]
    }.get(request_type, [])


def seed_requirements():
    catalog = [
        (
            "record_matricula",
            "Récord académico",
            "matricula_activa",
            "El estudiante debe tener matrícula activa.",
            True,
        ),
        (
            "record_paz_y_salvo",
            "Récord académico",
            "paz_y_salvo",
            "El estudiante debe estar a paz y salvo.",
            True,
        ),
        (
            "cert_matricula",
            "Certificación de estudio",
            "matricula_activa",
            "El estudiante debe tener matrícula activa.",
            True,
        ),
    ]

    for requirement in catalog:
        run(
            """
            INSERT INTO requirements (
                id,
                request_type,
                requirement_code,
                description,
                is_mandatory
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (request_type, requirement_code) DO NOTHING
            """,
            requirement,
        )


def validate_request(student, request_type):
    """Return named boolean checks; these rules are illustrative, not official policy."""
    requirements = get_requirements(request_type)
    labels = {
        "matricula_activa": "matrícula activa",
        "paz_y_salvo": "paz y salvo"
    }
    return {labels[r]: bool(student.get(r, False)) for r in requirements}

def create_request(student_id, request_type, status, notes, *, identity=None):

    if identity is None:
        raise PermissionError(
            "Acceso denegado. Se requiere una identidad verificada."
        )

    if identity.role != "admin":
        if (
            identity.role != "student"
            or identity.student_id != student_id
        ):
            raise PermissionError(
                "Acceso denegado. No puedes registrar "
                "solicitudes para otra matrícula."
            )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if database_url():
        row = run(
            "INSERT INTO requests VALUES ('UT-' || LPAD(nextval('request_number_seq')::text, 6, '0'), ?, ?, ?, ?, ?) RETURNING ticket",
            (student_id, request_type, status, now, notes), fetch="one"
        )
        return row["ticket"]
    last = run("SELECT ticket FROM requests ORDER BY ticket DESC LIMIT 1", fetch="one")
    number = int(last["ticket"].split("-")[1]) + 1 if last else 1
    ticket = f"UT-{number:06d}"
    run("INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?)", (ticket, student_id, request_type, status, now, notes))
    return ticket

def _get_request(ticket):
    """Consulta interna de solicitudes."""
    return run(
        "SELECT * FROM requests WHERE ticket = ?",
        (ticket,),
        fetch="one",
    )


def get_request(ticket, *, identity=None):
    """Consulta una solicitud únicamente si existe autorización."""
    request = _get_request(ticket)

    if request is None:
        return None

    if not can_view_request(identity, request):
        return None

    return request

def list_requests(*, identity=None):
    """Lista solicitudes únicamente para administradores autorizados."""
    if not can_manage_requests(identity):
        return []

    rows = run("""
        SELECT ticket AS "Ticket", student_id AS "Matrícula",
               request_type AS "Trámite", status AS "Estado",
               created_at AS "Fecha", notes AS "Observación"
        FROM requests ORDER BY created_at DESC, ticket DESC
    """, fetch="all")
    return rows

def faq_answer(question):
    """Responde preguntas frecuentes sin depender de la IA."""
    import unicodedata

    def normalize(text):
        text = unicodedata.normalize("NFKD", text.lower().strip())
        return "".join(
            char for char in text
            if not unicodedata.combining(char)
        )

    q = normalize(question)
    words = set(q.replace("¿", " ").replace("?", " ").split())

    # Saludos
    if words.intersection({"hola", "buenos", "buenas", "saludos"}):
        return (
            "¡Hola! Soy UniTramite AI, tu asistente virtual "
            "de atención estudiantil. Puedo orientarte sobre "
            "récords académicos, certificaciones de estudio, "
            "requisitos y seguimiento de solicitudes. "
            "¿En qué puedo ayudarte?"
        )

    # Trámites disponibles
    if (
        "tramites" in q
        or "servicios" in q
        or "que puedo realizar" in q
        or "que puedo hacer" in q
    ):
        return (
            "En UniTramite AI puedes recibir orientación sobre:\n\n"
            "1. Solicitud de récord académico.\n"
            "2. Certificación de estudio.\n"
            "3. Consulta y seguimiento de solicitudes.\n\n"
            "Este es un prototipo académico con datos ficticios. "
            "El registro y la consulta de solicitudes personales "
            "requieren autenticación, que todavía no está "
            "implementada en esta versión."
        )

    # Récord académico
    if any(
        term in q
        for term in ("record", "historial academico")
    ):
        return (
            "Para solicitar un récord académico, el prototipo "
            "contempla dos requisitos:\n\n"
            "1. Tener la matrícula activa.\n"
            "2. Estar a paz y salvo.\n\n"
            "UniTramite AI puede orientar sobre el trámite, "
            "pero el registro de solicitudes requiere una "
            "identidad autenticada. Actualmente esa función "
            "no está disponible para usuarios públicos.\n\n"
            "Los requisitos oficiales deben confirmarse "
            "directamente con la universidad."
        )

    # Certificaciones
    if any(
        term in q
        for term in (
            "certificacion",
            "certificado",
            "constancia",
        )
    ):
        return (
            "Para solicitar una certificación de estudio, "
            "el prototipo verifica que la matrícula esté activa.\n\n"
            "El estudiante puede recibir orientación mediante "
            "el chatbot, pero el registro de la solicitud "
            "requiere autenticación, todavía no disponible "
            "en esta versión.\n\n"
            "La emisión de documentos oficiales corresponde "
            "a la universidad."
        )

    # Paz y salvo
    if "paz y salvo" in q:
        return (
            "El paz y salvo es uno de los requisitos que "
            "el prototipo verifica para solicitar un récord "
            "académico. Si aparece pendiente, el caso debe "
            "revisarse con el personal administrativo. "
            "El chatbot no puede modificar estados financieros."
        )

    # Documentos oficiales
    if any(
        term in q
        for term in ("documento oficial", "emite", "oficial")
    ):
        return (
            "UniTramite AI es un prototipo académico. "
            "No emite documentos oficiales ni está conectado "
            "con los sistemas reales de la universidad."
        )

    # Seguimiento de solicitudes
    if any(
        term in q
        for term in ("estado", "seguimiento", "ticket", "solicitud")
    ):
        return (
            "UniTramite AI permite demostrar el seguimiento "
            "de solicitudes mediante tickets como UT-000001. "
            "Por privacidad, la consulta de información "
            "personal requiere autenticación, que todavía "
            "no está implementada en la interfaz pública."
        )

    # Respuesta de respaldo
    return (
        "Puedo orientarte sobre récords académicos, "
        "certificaciones de estudio, requisitos y seguimiento "
        "de solicitudes. ¿Sobre cuál de estos temas "
        "necesitas información?"
    )

def update_request_status(ticket, new_status, observation, *, identity=None):
    """Actualiza el estado y registra el cambio en el historial."""

     # Verificar permisos antes de modificar la solicitud
    if not can_manage_requests(identity):
        return (
            "Acceso denegado. Solo el personal administrativo "
            "autorizado puede actualizar solicitudes."
        )

    ticket = (ticket or "").strip().upper()
    new_status = (new_status or "").strip()
    observation = (observation or "").strip()

    allowed_statuses = {
        "Pendiente",
        "En proceso",
        "Completada",
        "Rechazada",
    }

    if new_status not in allowed_statuses:
        return "El estado seleccionado no es válido."

    if not observation:
        return "Debes escribir una observación para registrar el seguimiento."

    current = _get_request(ticket)

    if not current:
        return "No se encontró la solicitud indicada."

    previous_status = current["status"]

    if previous_status == new_status:
        return "La solicitud ya tiene ese estado."

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    previous_notes = current.get("notes") or ""

    # Conserva las observaciones anteriores y agrega la nueva.
    updated_notes = (
        f"{previous_notes}\n[{now}] {observation}"
        if previous_notes
        else f"[{now}] {observation}"
    )

    # Actualiza el estado y las observaciones actuales.
    run(
        """
        UPDATE requests
        SET status = ?, notes = ?
        WHERE ticket = ?
        """,
        (new_status, updated_notes, ticket),
    )

    # Registra el evento para conservar el historial.
    run(
        """
        INSERT INTO ticket_history
            (ticket, previous_status, new_status, observation, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ticket, previous_status, new_status, observation, now),
    )

    return None


def get_ticket_history(ticket, *, identity=None):
    """Consulta el historial únicamente con autorización."""

    ticket = (ticket or "").strip().upper()

    if not ticket or identity is None:
        return []

    request = get_request(
    ticket,
    identity=identity,
    )

    if not request:
        return []

    return run(
        """
        SELECT
            created_at AS "Fecha",
            previous_status AS "Estado anterior",
            new_status AS "Estado nuevo",
            observation AS "Observación"
        FROM ticket_history
        WHERE ticket = ?
        ORDER BY created_at DESC, id DESC
        """,
        (ticket,),
        fetch="all",
    )

def validate_ticket_format(ticket):
    return bool(re.fullmatch(r"UT-\d{6}", ticket or ""))


def detect_request_type(text):
    """Identifica solicitudes académicas mediante reglas y sinónimos."""
    import re
    import unicodedata

    if not text or not text.strip():
        return None

    # Normalizar mayúsculas, acentos y espacios.
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    record_patterns = [
        r"\brecord\b",
        r"\bhistorial academico\b",
        r"\bhistorial de notas\b",
        r"\bcalificaciones de todos los semestres\b",
        r"\brecord de calificaciones\b",
        r"\btodas mis notas\b",
    ]

    certificate_patterns = [
        r"\bcertificacion\b",
        r"\bcertificado\b",
        r"\bconstancia\b",
        r"\bcarta que confirme que estoy inscrito\b",
        r"\bcomprobante de matricula activa\b",
    ]

    record_match = any(
        re.search(pattern, normalized)
        for pattern in record_patterns
    )

    certificate_match = any(
        re.search(pattern, normalized)
        for pattern in certificate_patterns
    )

    # Evitar elegir automáticamente cuando aparecen ambos trámites.
    if record_match and certificate_match:
        return None

    if record_match:
        return "Récord académico"

    if certificate_match:
        return "Certificación de estudio"

    return None


def format_request(req):
    return (
        f"**Solicitud {req['ticket']}**\n\n"
        f"- Tipo: {req['request_type']}\n"
        f"- Estado: **{req['status']}**\n"
        f"- Fecha de creación: {req['created_at']}\n"
        f"- Observación: {req['notes']}"
    )


def register_document(
    ticket,
    requirement_code,
    file_name,
    observations="",
    *,
    identity=None,
):
    """Registra documentos únicamente con autorización administrativa."""

    if not can_manage_documents(identity):
        return (
            "Acceso denegado. Solo el personal administrativo "
            "autorizado puede registrar documentos."
        )


    ticket = (ticket or "").strip().upper()
    requirement_code = (requirement_code or "").strip()
    file_name = (file_name or "").strip()
    observations = (observations or "").strip()

    if not ticket:
        return "Debes indicar el ticket de la solicitud."

    if not requirement_code:
        return "Debes seleccionar un requisito."

    if not file_name:
        return "Debes indicar el nombre del documento."

    # Verificar que la solicitud exista.
    request = get_request(ticket, identity=identity)

    if not request:
        return "No se encontró la solicitud indicada."

    # Verificar que el requisito corresponda al trámite.
    requirement = run(
        """
        SELECT requirement_code
        FROM requirements
        WHERE request_type = ?
          AND requirement_code = ?
        """,
        (request["request_type"], requirement_code),
        fetch="one",
    )

    if not requirement:
        return (
            "El requisito seleccionado no corresponde "
            "al tipo de trámite de esta solicitud."
        )

    document_id = str(uuid.uuid4())
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    run(
        """
        INSERT INTO documents (
            id,
            ticket,
            requirement_code,
            file_name,
            status,
            observations,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            ticket,
            requirement_code,
            file_name,
            "Pendiente",
            observations,
            created_at,
        ),
    )

    return None

def list_documents(ticket, *, identity=None):
    """Consulta los documentos asociados a una solicitud."""

    ticket = (ticket or "").strip().upper()

    if not ticket:
        return []

    if identity is None:
        return []

    request = get_request(ticket, identity=identity)

    if not request:
        return []


    return run(
        """
        SELECT
            id AS "ID",
            ticket AS "Ticket",
            requirement_code AS "Código de requisito",
            file_name AS "Documento",
            status AS "Estado",
            observations AS "Observaciones",
            created_at AS "Fecha de registro"
        FROM documents
        WHERE ticket = ?
        ORDER BY created_at DESC, id DESC
        """,
        (ticket,),
        fetch="all",
    )


def update_document_status(
    document_id,
    new_status,
    observations,
    *,
    identity=None,
):
    """Actualiza documentos únicamente con autorización administrativa."""

    if not can_manage_documents(identity):
        return (
            "Acceso denegado. Solo el personal administrativo "
            "autorizado puede actualizar documentos."
        )


    document_id = (document_id or "").strip()
    new_status = (new_status or "").strip().casefold()
    observations = (observations or "").strip()

    estados_permitidos = {
        "pendiente": "Pendiente",
        "aprobado": "Aprobado",
        "rechazado": "Rechazado",
    }

    if not document_id:
        return "Debes seleccionar un documento."

    if new_status not in estados_permitidos:
        return (
            "Estado no válido. Utiliza Pendiente, "
            "Aprobado o Rechazado."
        )

    if not observations:
        return "Debes registrar una observación de revisión."

    document = run(
        "SELECT id FROM documents WHERE id = ?",
        (document_id,),
        fetch="one",
    )

    if not document:
        return "No se encontró el documento indicado."

    status = estados_permitidos[new_status]

    run(
        """
        UPDATE documents
        SET status = ?, observations = ?
        WHERE id = ?
        """,
        (status, observations, document_id),
    )

    return None

def register_request(student_id, request_type, *, identity=None):
    """Validate the student and store the request; returns the chatbot reply."""

    if identity is None:
        return (
            "Acceso denegado. Debes iniciar sesión "
            "con una identidad verificada para registrar solicitudes."
        )

    if identity.role != "admin":
        if (
            identity.role != "student"
            or identity.student_id != student_id
        ):
            return (
                "Acceso denegado. No puedes registrar "
                "solicitudes para otra matrícula."
            )

    student = get_student(student_id, identity=identity)
    checks = validate_request(student, request_type)
    missing = [name for name, ok in checks.items() if not ok]
    if missing:

        ticket = create_request(
            student_id,
            request_type,
            "Pendiente de revisión",
            "No cumple: " + ", ".join(missing),
            identity=identity,
        )

        return (
            f"Registré la solicitud **{ticket}**, pero queda **Pendiente de revisión**.\n\n"
            f"Validaciones que requieren atención: {', '.join(missing)}.\n\n"
            "El prototipo no rechaza definitivamente la solicitud ni sustituye la revisión de la oficina académica."
        )

    ticket = create_request(
        student_id,
        request_type,
        "Recibida",
        "Validaciones simuladas completadas; pendiente de revisión institucional.",
        identity=identity,
    )

    return (
        f"Las validaciones simuladas se completaron y registré la solicitud **{ticket}** con estado **Recibida**.\n\n"
        "Esto no significa que el documento haya sido emitido. La oficina académica debe procesar la solicitud."
    )

def detect_confirmation(prompt):
    """Identifica respuestas explícitas de confirmación o cancelación."""
    text = prompt.strip().lower()

    if text in ("confirmar", "confirmo", "sí, confirmar", "si, confirmar"):
        return "confirm"

    if text in ("cancelar", "cancelo", "no, cancelar"):
        return "cancel"

    return None

def handle_message(prompt, state):
    """Return the chatbot reply. `state` keeps pending_type/pending_student between turns and is updated in place."""
        # Permitir cancelar un trámite en cualquier etapa.
    if detect_confirmation(prompt) == "cancel":
        if state.get("pending_type") or state.get("pending_student"):
            state["pending_type"] = None
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return "La solicitud fue cancelada. No se generó ningún ticket."

        return "No tienes ninguna solicitud pendiente para cancelar."

    ticket_match = re.search(r"UT-\d{6}", prompt.upper())

    if ticket_match:
        # La identidad debe provenir de una sesión autenticada
        # por un mecanismo confiable, nunca del texto del chat.
        identity = state.get("authenticated_identity")

        if identity is None:
            return (
                "Para consultar información de una solicitud "
                "debes iniciar sesión con una identidad verificada. "
                "Este prototipo todavía no dispone de "
                "autenticación real."
            )

        req = get_request(
            ticket_match.group(0),
            identity=identity,
        )
        if not req:
            return (
                "No se puede mostrar la solicitud indicada. "
                "Verifica tus permisos o contacta al "
                "personal autorizado."
            )


        return format_request(req)


    request_type = detect_request_type(prompt)
    if request_type:
        state["pending_type"] = request_type
    student_match = re.search(r"\b\d{4}-\d{4}\b", prompt)

    if student_match:
        student_id = student_match.group(0)
        identity = state.get("authenticated_identity")

        if identity is None:
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return (
                "Para utilizar una matrícula debes iniciar sesión "
                "con una identidad verificada. "
                "Este prototipo todavía no dispone de autenticación real."
            )

        if (
            identity.role != "admin"
            and (
                identity.role != "student"
                or identity.student_id != student_id
            )
        ):
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return (
                "Acceso denegado. No puedes utilizar "
                "una matrícula diferente a la autorizada."
            )

        if not get_student(student_id, identity=identity):
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return (
                "No se encontró la matrícula indicada. "
                "Contacta al personal administrativo."
            )

        state["pending_student"] = student_id


    if state.get("pending_type") and state.get("pending_student"):
        decision = detect_confirmation(prompt)

        if decision == "cancel":
            state["pending_type"] = None
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return "La solicitud fue cancelada. No se generó ningún ticket."


        if decision == "confirm" and state.get("pending_confirmation"):
            # La identidad debe provenir de una autenticación real,
            # nunca de la matrícula escrita en el chatbot.
            identity = state.get("authenticated_identity")

            if identity is None:
                return (
                    "Para registrar una solicitud necesitas "
                    "autenticación con una identidad verificada. "
                    "Este prototipo todavía no dispone de "
                    "autenticación real."
                )

            if (
                identity.role != "admin"
                and (
                    identity.role != "student"
                    or identity.student_id != state["pending_student"]
                )
            ):
                return (
                    "Acceso denegado. No puedes registrar "
                    "solicitudes para otra matrícula."
                )

            response = register_request(
                state["pending_student"],
                state["pending_type"],
                identity=identity,
            )

            state["pending_type"] = None
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return response

        state["pending_confirmation"] = True

        return (
            "**Confirma los datos de tu solicitud:**\n\n"
            f"- Trámite: {state['pending_type']}\n"
            f"- Matrícula: {state['pending_student']}\n\n"
            "Escribe **confirmar** para registrar la solicitud "
            "o **cancelar** para descartarla."
        )

    if request_type == "Récord académico":
        return "Puedo registrar una solicitud de récord académico. Para la demostración, escribe tu matrícula ficticia (ej.: 2024-1001). No compartas datos personales reales."
    if request_type == "Certificación de estudio":
        return "Puedo registrar una solicitud de certificación de estudio. Escribe tu matrícula ficticia (ej.: 2024-1001). No uses datos personales reales."
    if student_match:
        return f"Tengo tu matrícula **{state['pending_student']}**. ¿Qué trámite necesitas: récord académico o certificación de estudio?"
    if any(k in prompt.lower() for k in ["estado", "seguimiento", "ticket", "solicitud"]):
        return "Para consultar el estado, envíame el identificador del ticket (formato UT-000001). También puedes usar la sección «Consultar una solicitud»."
    return faq_answer(prompt)
