import os
import sqlite3
from pathlib import Path
from datetime import datetime
import json
import re

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

def validate_ticket_format(ticket):
    return bool(re.fullmatch(r"UT-\d{6}", ticket or ""))

def detect_request_type(text):
    t = text.lower()
    if any(k in t for k in ["récord", "record", "historial académico"]):
        return "Récord académico"
    if any(k in t for k in ["certificación", "certificacion", "certificado", "constancia", "estudio"]):
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

def handle_message(prompt, state):
    """Return the chatbot reply. `state` keeps pending_type/pending_student between turns and is updated in place."""
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
        response = register_request(state["pending_student"], state["pending_type"])
        state["pending_type"] = state["pending_student"] = None
        return response
    if request_type == "Récord académico":
        return "Puedo registrar una solicitud de récord académico. Para la demostración, escribe tu matrícula ficticia (ej.: 2024-1001). No compartas datos personales reales."
    if request_type == "Certificación de estudio":
        return "Puedo registrar una solicitud de certificación de estudio. Escribe tu matrícula ficticia (ej.: 2024-1001). No uses datos personales reales."
    if student_match:
        return f"Tengo tu matrícula **{state['pending_student']}**. ¿Qué trámite necesitas: récord académico o certificación de estudio?"
    if any(k in prompt.lower() for k in ["estado", "seguimiento", "ticket", "solicitud"]):
        return "Para consultar el estado, envíame el identificador del ticket (formato UT-000001). También puedes usar la sección «Consultar una solicitud»."
    return faq_answer(prompt)
