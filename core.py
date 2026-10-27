import os
import sqlite3
from pathlib import Path
from datetime import datetime
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
                register_student(student_id, s["nombre"], s["matricula_activa"], s["paz_y_salvo"], s["nota"])
    if run("SELECT COUNT(*) AS n FROM requests", fetch="one")["n"] == 0:
        run("INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?)", SEED_REQUEST)

def validate_student_id_format(student_id):
    return bool(re.fullmatch(r"\d{4}-\d{4}", student_id or ""))

def get_student(student_id):
    row = run("SELECT * FROM students WHERE student_id = ?", (student_id,), fetch="one")
    if row:
        # SQLite returns booleans as 0/1
        row["matricula_activa"] = bool(row["matricula_activa"])
        row["paz_y_salvo"] = bool(row["paz_y_salvo"])
    return row

def register_student(student_id, full_name, matricula_activa, paz_y_salvo, notes=""):
    """Store a new student; returns an error message, or None when it was saved."""
    student_id = (student_id or "").strip()
    full_name = (full_name or "").strip()
    if not validate_student_id_format(student_id):
        return "La matrícula debe tener el formato 0000-0000."
    if not full_name:
        return "El nombre es obligatorio."
    if get_student(student_id):
        return f"La matrícula {student_id} ya está registrada."
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    run("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)",
        (student_id, full_name, bool(matricula_activa), bool(paz_y_salvo), notes.strip(), now))
    return None

def list_students():
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

def create_request(student_id, request_type, status, notes):
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

def get_request(ticket):
    return run("SELECT * FROM requests WHERE ticket = ?", (ticket,), fetch="one")

def list_requests():
    return run("""
        SELECT ticket AS "Ticket", student_id AS "Matrícula",
               request_type AS "Trámite", status AS "Estado",
               created_at AS "Fecha", notes AS "Observación"
        FROM requests ORDER BY created_at DESC, ticket DESC
    """, fetch="all")

def faq_answer(question):
    q = question.lower()
    if any(k in q for k in ["récord", "record", "historial académico"]):
        return "Puedes solicitar un récord académico desde el chatbot. El prototipo verifica matrícula activa y paz y salvo con datos ficticios y registra un ticket. Los requisitos reales deben confirmarse con la universidad."
    if any(k in q for k in ["certificación", "certificado", "constancia"]):
        return "Puedes solicitar una certificación de estudio. En esta demostración se verifica la matrícula activa. La emisión oficial corresponde al área académica."
    if any(k in q for k in ["estado", "seguimiento", "ticket", "solicitud"]):
        return "Para consultar una solicitud, introduce su identificador, por ejemplo UT-000001, en la sección de seguimiento."
    if "paz y salvo" in q:
        return "Si tu paz y salvo aparece pendiente, el chatbot registra el caso para revisión. No puede modificar estados financieros ni conceder excepciones."
    if any(k in q for k in ["emite", "documento oficial", "oficial"]):
        return "No. Este prototipo registra solicitudes y demuestra validaciones. No emite documentos oficiales ni tiene conexión con los sistemas universitarios."
    return "Puedo orientarte sobre récords académicos, certificaciones y seguimiento de solicitudes. Si tu caso requiere una decisión administrativa, debe revisarlo el personal autorizado."

def update_request_status(ticket, new_status, observation):
    """Actualiza el estado y registra el cambio en el historial."""

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

    current = get_request(ticket)

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


def get_ticket_history(ticket):
    """Devuelve el historial de seguimiento de un ticket."""

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

def register_document(ticket, requirement_code, file_name, observations=""):
    """Registra los metadatos de un documento asociado a una solicitud."""

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
    request = get_request(ticket)

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

def list_documents(ticket):
    """Consulta los documentos asociados a una solicitud."""

    ticket = (ticket or "").strip().upper()

    if not ticket:
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

def update_document_status(document_id, new_status, observations):
    """Actualiza el estado y las observaciones de un documento."""

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

def register_request(student_id, request_type):
    """Validate the student and store the request; returns the chatbot reply."""
    student = get_student(student_id)
    checks = validate_request(student, request_type)
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        ticket = create_request(student_id, request_type, "Pendiente de revisión", "No cumple: " + ", ".join(missing))
        return (
            f"Registré la solicitud **{ticket}**, pero queda **Pendiente de revisión**.\n\n"
            f"Validaciones que requieren atención: {', '.join(missing)}.\n\n"
            "El prototipo no rechaza definitivamente la solicitud ni sustituye la revisión de la oficina académica."
        )
    ticket = create_request(student_id, request_type, "Recibida", "Validaciones simuladas completadas; pendiente de revisión institucional.")
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
        req = get_request(ticket_match.group(0))
        if req:
            return format_request(req)
        return "No encontré ese ticket en la base de datos simulada. Verifica el identificador o solicita ayuda al personal de atención."

    request_type = detect_request_type(prompt)
    if request_type:
        state["pending_type"] = request_type
    student_match = re.search(r"\b\d{4}-\d{4}\b", prompt)
    if student_match:
        if not get_student(student_match.group(0)):
            state["pending_student"] = None
            return "La matrícula no está registrada. Regístrala en «Registro de estudiantes» o prueba con 2024-1001, 2024-1002 o 2023-2040."
        state["pending_student"] = student_match.group(0)


    if state.get("pending_type") and state.get("pending_student"):
        decision = detect_confirmation(prompt)

        if decision == "cancel":
            state["pending_type"] = None
            state["pending_student"] = None
            state["pending_confirmation"] = False
            return "La solicitud fue cancelada. No se generó ningún ticket."

        if decision == "confirm" and state.get("pending_confirmation"):
            response = register_request(
                state["pending_student"],
                state["pending_type"]
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
