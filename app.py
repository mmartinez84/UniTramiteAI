import os
import streamlit as st
from core import (
    init_db, get_request,
    list_requests, faq_answer, handle_message,
    register_student, list_students
)

st.set_page_config(page_title="UniTramite AI | Atención a Estudiantes", page_icon="🎓", layout="wide")

# En Streamlit Cloud (o .streamlit/secrets.toml) la URL de PostgreSQL llega como secreto
if st.secrets.load_if_toml_exists() and "DATABASE_URL" in st.secrets:
    os.environ.setdefault("DATABASE_URL", st.secrets["DATABASE_URL"])

@st.cache_resource
def setup_database():
    init_db()

setup_database()

st.title("🎓 Chatbot de Atención a Estudiantes")
st.caption("UniTramite AI · Prototipo académico con datos simulados")
st.warning("Demostración: no conecta con sistemas reales de la universidad. Usa exclusivamente los estudiantes y tickets ficticios incluidos.")

with st.sidebar:
    st.header("Menú")
    section = st.radio("Selecciona una función", [
        "Conversar con el chatbot",
        "Consultar una solicitud",
        "Panel de solicitudes",
        "Registro de estudiantes",
        "Preguntas frecuentes",
        "Acerca del prototipo"
    ])
    st.divider()
    st.caption("Versión 0.1 · Canal web activo")

if section == "Conversar con el chatbot":
    st.subheader("Atención conversacional")
    st.write("Puedes solicitar un récord académico, una certificación de estudio o ayuda para consultar un ticket.")
    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant",
            "content": "¡Hola! Soy UniTramite AI. Puedo ayudarte con récords académicos, certificaciones y seguimiento de solicitudes. Para empezar, indícame tu matrícula ficticia (por ejemplo, 2024-1001) y qué trámite necesitas."
        }]
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if "chat_state" not in st.session_state:
        st.session_state.chat_state = {"pending_type": None, "pending_student": None}

    prompt = st.chat_input("Escribe tu consulta...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        response = handle_message(prompt, st.session_state.chat_state)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

elif section == "Consultar una solicitud":
    st.subheader("Seguimiento por ticket")
    ticket = st.text_input("Identificador de ticket", placeholder="UT-000001").strip().upper()
    if st.button("Consultar", type="primary"):
        if not ticket:
            st.info("Introduce un identificador.")
        else:
            req = get_request(ticket)
            if req:
                st.success(f"Estado: {req['status']}")
                st.write(f"**Tipo:** {req['request_type']}")
                st.write(f"**Fecha:** {req['created_at']}")
                st.write(f"**Observación:** {req['notes']}")
            else:
                st.error("No se encontró el ticket en la base simulada.")

elif section == "Panel de solicitudes":
    st.subheader("Panel de control — datos ficticios")
    rows = list_requests()
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("Los tickets son demostrativos. En producción, este panel requeriría autenticación y permisos por rol.")
    else:
        st.info("Todavía no hay solicitudes. Crea una desde el chatbot.")

elif section == "Registro de estudiantes":
    st.subheader("Registro de estudiantes — datos ficticios")
    st.caption("Sección pensada para el personal. Usa solo datos inventados: en producción el estado de matrícula y el paz y salvo vendrían de los sistemas de la universidad y esta sección requeriría autenticación.")
    with st.form("registro_estudiante", clear_on_submit=True):
        col1, col2 = st.columns(2)
        student_id = col1.text_input("Matrícula", placeholder="2025-0001")
        full_name = col2.text_input("Nombre completo")
        matricula_activa = col1.checkbox("Matrícula activa", value=True)
        paz_y_salvo = col2.checkbox("Paz y salvo al día", value=True)
        notes = st.text_input("Nota (opcional)")
        if st.form_submit_button("Registrar estudiante", type="primary"):
            error = register_student(student_id, full_name, matricula_activa, paz_y_salvo, notes)
            if error:
                st.error(error)
            else:
                st.success(f"Estudiante {student_id.strip()} registrado. Ya puede solicitar trámites en el chatbot.")
    st.dataframe(list_students(), use_container_width=True, hide_index=True)

elif section == "Preguntas frecuentes":
    st.subheader("Preguntas frecuentes")
    questions = [
        "¿Cómo solicito un récord académico?",
        "¿Cómo solicito una certificación de estudio?",
        "¿Cómo consulto el estado de mi solicitud?",
        "¿El chatbot emite documentos oficiales?",
        "¿Qué hago si mi paz y salvo está pendiente?"
    ]
    for q in questions:
        with st.expander(q):
            st.write(faq_answer(q))

else:
    st.subheader("Alcance y limitaciones")
    st.markdown("""
**Incluido en esta versión**
- Interfaz web conversacional.
- Tres flujos: récord académico, certificación y seguimiento de tickets.
- Reglas deterministas sobre datos ficticios.
- Registro de estudiantes y solicitudes en SQLite local o PostgreSQL (Supabase).
- Panel básico de solicitudes.

**No incluido todavía**
- LLM conectado a un proveedor.
- WhatsApp Business API activa.
- Integración con sistemas académicos reales.
- Autenticación real de estudiantes.
- Emisión o firma de documentos oficiales.

**Principio de seguridad:** el chatbot no debe inventar datos ni afirmar que emitió un documento cuando solo registró una solicitud.
""")
