import os
import streamlit as st
from chat_router import route_message
from dashboard import show_dashboard
from core import (
    init_db,
    get_request,
    list_requests,
    faq_answer,
    handle_message,
    register_student,
    list_students,
    update_request_status,
    get_ticket_history,
    register_document,
    list_documents,
    update_document_status,
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
        "Dashboard Analítico",
        "Registro de estudiantes",
        "Gestión de documentos",
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
        response = route_message(prompt, st.session_state.chat_state)
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
    st.subheader("Panel de seguimiento de solicitudes")
    st.caption(
        "Consulta, filtra, actualiza y revisa las solicitudes "
        "registradas en el prototipo UniTramite AI."
    )

    # Mostrar mensajes después de una actualización.
    mensaje_actualizacion = st.session_state.pop(
        "mensaje_actualizacion_solicitud", None
    )
    if mensaje_actualizacion:
        st.success(mensaje_actualizacion)

    rows = list_requests()

    if rows:
        import pandas as pd

        df = pd.DataFrame(rows)

        # Normalizar valores para búsqueda y filtros.
        df["Estado"] = df["Estado"].fillna("").astype(str).str.strip()
        df["Trámite"] = df["Trámite"].fillna("").astype(str).str.strip()
        df["Ticket"] = df["Ticket"].fillna("").astype(str).str.strip()
        df["Matrícula"] = (
            df["Matrícula"].fillna("").astype(str).str.strip()
        )

        # Indicadores generales.
        total = len(df)
        estados = df["Estado"].str.casefold()

        pendientes = int(
            estados.isin(["pendiente", "pendientes"]).sum()
        )

        completadas = int(
            estados.isin([
                "completada",
                "completado",
                "completadas",
                "completados",
                "finalizada",
                "finalizado",
                "resuelta",
                "resuelto",
            ]).sum()
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de solicitudes", total)
        col2.metric("Pendientes", pendientes)
        col3.metric("Completadas", completadas)

        st.divider()

        # Búsqueda y filtros.
        st.markdown("### Buscar y filtrar")

        col_busqueda, col_tipo, col_estado = st.columns([2, 1, 1])

        with col_busqueda:
            busqueda = st.text_input(
                "Buscar por matrícula o ticket",
                placeholder="Ej.: 2024-1001 o UT-000001",
            ).strip().casefold()

        with col_tipo:
            tipos = sorted(
                [valor for valor in df["Trámite"].unique() if valor]
            )
            tipo_seleccionado = st.selectbox(
                "Tipo de trámite",
                ["Todos"] + tipos,
            )

        with col_estado:
            estados_disponibles = sorted(
                [valor for valor in df["Estado"].unique() if valor]
            )
            estado_seleccionado = st.selectbox(
                "Estado",
                ["Todos"] + estados_disponibles,
            )

        filtrado = df.copy()

        if busqueda:
            coincidencias = (
                filtrado["Matrícula"].str.casefold().str.contains(
                    busqueda, regex=False
                )
                | filtrado["Ticket"].str.casefold().str.contains(
                    busqueda, regex=False
                )
            )
            filtrado = filtrado[coincidencias]

        if tipo_seleccionado != "Todos":
            filtrado = filtrado[
                filtrado["Trámite"] == tipo_seleccionado
            ]

        if estado_seleccionado != "Todos":
            filtrado = filtrado[
                filtrado["Estado"] == estado_seleccionado
            ]

        st.markdown("### Resultados")
        st.caption(
            f"Se encontraron {len(filtrado)} de {total} solicitudes."
        )

        if not filtrado.empty:
            st.dataframe(
                filtrado,
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.markdown("### Detalle y seguimiento de la solicitud")

            tickets = filtrado["Ticket"].tolist()

            ticket_seleccionado = st.selectbox(
                "Selecciona una solicitud",
                tickets,
                key="ticket_seleccionado_panel",
            )

            solicitud = get_request(ticket_seleccionado)

            if solicitud:
                st.write(f"**Ticket:** {solicitud['ticket']}")
                st.write(f"**Matrícula:** {solicitud['student_id']}")
                st.write(f"**Tipo de trámite:** {solicitud['request_type']}")
                st.write(f"**Estado actual:** {solicitud['status']}")
                st.write(f"**Fecha de creación:** {solicitud['created_at']}")
                st.write(
                    f"**Observaciones registradas:** "
                    f"{solicitud['notes'] or 'Sin observaciones'}"
                )

                # Actualización de estado y registro del seguimiento.
                st.markdown("#### Actualizar estado")

                estados_permitidos = [
                    "Pendiente",
                    "En proceso",
                    "Completada",
                    "Rechazada",
                ]

                estado_actual = solicitud["status"]

                # Mantener visible el estado actual aunque no esté
                # incluido entre las opciones estándar.
                if estado_actual not in estados_permitidos:
                    estados_permitidos.insert(0, estado_actual)

                with st.form(
                    "form_actualizar_solicitud",
                    clear_on_submit=True,
                ):
                    nuevo_estado = st.selectbox(
                        "Nuevo estado",
                        estados_permitidos,
                        index=estados_permitidos.index(estado_actual),
                    )

                    observacion = st.text_area(
                        "Observación del seguimiento",
                        placeholder=(
                            "Describe la gestión realizada, "
                            "el motivo del cambio o el próximo paso."
                        ),
                    )

                    confirmar = st.form_submit_button(
                        "Guardar actualización"
                    )

                    if confirmar:
                        if not observacion.strip():
                            st.error(
                                "Debes escribir una observación "
                                "para registrar el seguimiento."
                            )
                        else:
                            resultado = update_request_status(
                                ticket_seleccionado,
                                nuevo_estado,
                                observacion,
                            )

                            if resultado:
                                st.error(resultado)
                            else:
                                st.session_state[
                                    "mensaje_actualizacion_solicitud"
                                ] = (
                                    f"Solicitud {ticket_seleccionado} "
                                    f"actualizada correctamente."
                                )
                                st.rerun()

                # Historial de seguimiento.
                st.markdown("#### Historial de seguimiento")

                historial = get_ticket_history(ticket_seleccionado)

                if historial:
                    df_historial = pd.DataFrame(historial)

                    st.dataframe(
                        df_historial,
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "Esta solicitud todavía no tiene cambios "
                        "registrados en el historial."
                    )

        else:
            st.info(
                "No se encontraron solicitudes con los criterios "
                "de búsqueda seleccionados."
            )

        st.caption(
            "Los datos pertenecen al prototipo. En un entorno real, "
            "el acceso a los expedientes requeriría autenticación "
            "y permisos adecuados."
        )

    else:
        st.info(
            "Todavía no hay solicitudes registradas. "
            "Crea una desde el chatbot para comenzar."
        )
elif section == "Dashboard Analítico":
    show_dashboard()

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

elif section == "Gestión de documentos":
    st.subheader("Gestión de documentos")
    st.caption(
        "Registra documentos, consulta su estado y "
        "gestiona las observaciones de revisión."
    )

    # Obtener solicitudes existentes.
    solicitudes = list_requests()

    if not solicitudes:
        st.info(
            "No hay solicitudes registradas. "
            "Crea una solicitud antes de registrar documentos."
        )

    else:
        import pandas as pd

        df_solicitudes = pd.DataFrame(solicitudes)

        tickets = df_solicitudes["Ticket"].tolist()

        ticket = st.selectbox(
            "Selecciona el ticket de la solicitud",
            tickets,
            key="ticket_documentos",
        )

        solicitud = get_request(ticket)

        if solicitud:
            st.write(f"**Matrícula:** {solicitud['student_id']}")
            st.write(f"**Tipo de trámite:** {solicitud['request_type']}")
            st.write(f"**Estado de la solicitud:** {solicitud['status']}")

            # Obtener los requisitos del trámite.
            from core import get_requirements

            requisitos = get_requirements(solicitud["request_type"])

            st.divider()
            st.markdown("### Registrar documento")

            if requisitos:
                with st.form("form_registrar_documento"):
                    requisito = st.selectbox(
                        "Requisito asociado",
                        requisitos,
                    )

                    nombre_documento = st.text_input(
                        "Nombre del documento",
                        placeholder="Ej.: constancia_matricula.pdf",
                    )

                    observaciones = st.text_area(
                        "Observaciones iniciales",
                        placeholder="Información adicional del documento.",
                    )

                    registrar = st.form_submit_button(
                        "Registrar documento"
                    )

                    if registrar:
                        resultado = register_document(
                            ticket=ticket,
                            requirement_code=requisito,
                            file_name=nombre_documento,
                            observations=observaciones,
                        )

                        if resultado:
                            st.error(resultado)
                        else:
                            st.session_state[
                                "mensaje_documento"
                            ] = "Documento registrado correctamente."
                            st.rerun()

            else:
                st.warning(
                    "Este tipo de trámite no tiene requisitos "
                    "configurados en el catálogo."
                )

            # Mostrar confirmación después de registrar.
            mensaje = st.session_state.pop(
                "mensaje_documento", None
            )

            if mensaje:
                st.success(mensaje)

            st.divider()
            st.markdown("### Documentos registrados")

            documentos = list_documents(ticket)

            if documentos:
                df_documentos = pd.DataFrame(documentos)

                st.dataframe(
                    df_documentos.drop(columns=["ID"]),
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown("### Revisar documento")

                documentos_por_id = {
                    f"{doc['Documento']} — {doc['ID'][:8]}": doc
                    for doc in documentos
                }

                seleccion = st.selectbox(
                    "Selecciona el documento que deseas revisar",
                    list(documentos_por_id.keys()),
                    key="documento_seleccionado",
                )

                documento = documentos_por_id[seleccion]

                with st.form("form_actualizar_documento"):
                    nuevo_estado = st.selectbox(
                        "Estado de validación",
                        ["Pendiente", "Aprobado", "Rechazado"],
                        index=[
                            "Pendiente",
                            "Aprobado",
                            "Rechazado",
                        ].index(documento["Estado"])
                        if documento["Estado"] in [
                            "Pendiente",
                            "Aprobado",
                            "Rechazado",
                        ]
                        else 0,
                    )

                    observacion_revision = st.text_area(
                        "Observación de revisión",
                        value=documento["Observaciones"] or "",
                    )

                    actualizar = st.form_submit_button(
                        "Guardar revisión"
                    )

                    if actualizar:
                        resultado = update_document_status(
                            document_id=documento["ID"],
                            new_status=nuevo_estado,
                            observations=observacion_revision,
                        )

                        if resultado:
                            st.error(resultado)
                        else:
                            st.session_state[
                                "mensaje_revision_documento"
                            ] = "Revisión guardada correctamente."
                            st.rerun()

                mensaje_revision = st.session_state.pop(
                    "mensaje_revision_documento", None
                )

                if mensaje_revision:
                    st.success(mensaje_revision)

            else:
                st.info(
                    "Esta solicitud todavía no tiene documentos registrados."
                )
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
