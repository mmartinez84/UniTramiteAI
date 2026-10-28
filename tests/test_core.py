import os
import tempfile
import unittest
from pathlib import Path
import core
from core import get_student, validate_request, validate_ticket_format

class TestCore(unittest.TestCase):
    def setUp(self):
        self.original_url = os.environ.pop("DATABASE_URL", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db = core.DB_PATH
        core.DB_PATH = Path(self.tmp.name) / "test.db"
        core.init_db()

    def test_list_students_requires_admin_authorization(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )
        admin = Identity(role="admin")

        # Un usuario anónimo no puede listar estudiantes.
        self.assertEqual(core.list_students(), [])

        # Un estudiante tampoco puede listar estudiantes.
        self.assertEqual(
            core.list_students(identity=student),
            [],
        )

        # Un administrador puede consultar el listado.
        students = core.list_students(identity=admin)

        self.assertGreater(len(students), 0)

        self.assertTrue(
            any(
                row["Matrícula"] == "2024-1001"
                for row in students
            )
        )
    def test_student_cannot_register_another_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        result = core.register_student(
            "2025-0099",
            "Estudiante No Autorizado",
            True,
            True,
            identity=student,
        )

        self.assertIn(
            "Acceso denegado",
            result,
        )

        admin = Identity(role="admin")

        self.assertIsNone(
            core.get_student(
                "2025-0099",
                identity=admin,
            )
        )
    def test_register_student_without_identity_does_not_save(self):
        from security import Identity

        result = core.register_student(
            "2025-0098",
            "Estudiante No Autorizado",
            True,
            True,
        )

        self.assertIn("Acceso denegado", result)

        admin = Identity(role="admin")

        self.assertIsNone(
            core.get_student(
                "2025-0098",
                identity=admin,
            )
        )
    def tearDown(self):
        core.DB_PATH = self.original_db
        self.tmp.cleanup()
        if self.original_url:
            os.environ["DATABASE_URL"] = self.original_url

    def test_student_exists(self):
        from security import Identity

        admin = Identity(role="admin")

        self.assertIsNotNone(
            get_student("2024-1001", identity=admin)
        )

    def test_record_requires_active_and_clearance(self):
        from security import Identity

        admin = Identity(role="admin")

        student = get_student("2024-1002", identity=admin)

        result = validate_request(student, "Récord académico")

        self.assertTrue(result["matrícula activa"])
        self.assertFalse(result["paz y salvo"])

    def test_certificate_requires_active_enrollment(self):
        from security import Identity

        admin = Identity(role="admin")

        student = get_student("2023-2040", identity=admin)

        result = validate_request(student, "Certificación de estudio")

        self.assertFalse(result["matrícula activa"])

    def test_get_student_requires_authorization(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        other_student = Identity(
            student_id="2024-1002",
            role="student",
        )

        admin = Identity(role="admin")

        # Un usuario anónimo no puede consultar estudiantes.
        self.assertIsNone(
            core.get_student("2024-1001")
        )

        # Un estudiante puede consultar sus propios datos.
        own_data = core.get_student(
            "2024-1001",
            identity=student,
        )

        self.assertIsNotNone(own_data)
        self.assertEqual(
            own_data["student_id"],
            "2024-1001",
        )

        # Un estudiante no puede consultar otra matrícula.
        self.assertIsNone(
            core.get_student(
                "2024-1002",
                identity=student,
            )
        )

        # Otro estudiante tampoco puede consultar la primera.
        self.assertIsNone(
            core.get_student(
                "2024-1001",
                identity=other_student,
            )
        )

        # Un administrador puede consultar ambas matrículas.
        self.assertIsNotNone(
            core.get_student(
                "2024-1001",
                identity=admin,
            )
        )

        self.assertIsNotNone(
            core.get_student(
                "2024-1002",
                identity=admin,
            )
        )

    def test_ticket_format(self):
        self.assertTrue(validate_ticket_format("UT-000123"))
        self.assertFalse(validate_ticket_format("ticket123"))

class TestChatSavesRequests(unittest.TestCase):
    """Runs on a temporary SQLite file."""
    def setUp(self):
        self.original_url = os.environ.pop("DATABASE_URL", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db = core.DB_PATH
        core.DB_PATH = Path(self.tmp.name) / "test.db"
        core.init_db()
        self.state = {"pending_type": None, "pending_student": None}

    def test_create_request_direct_call_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        ticket = core.create_request(
            "2024-1001",
            "Récord académico",
            "Recibida",
            "Solicitud administrativa de prueba",
            identity=admin,
        )

        self.assertEqual(ticket, "UT-000002")

        request = core.get_request(
            ticket,
            identity=admin,
        )

        self.assertIsNotNone(request)
        self.assertEqual(
            request["student_id"],
            "2024-1001",
        )
        self.assertEqual(
            request["request_type"],
            "Récord académico",
        )
        self.assertEqual(
            request["status"],
            "Recibida",
        )

    def test_create_request_direct_call_by_owner(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        ticket = core.create_request(
            "2024-1001",
            "Récord académico",
            "Recibida",
            "Solicitud autorizada de prueba",
            identity=student,
        )

        self.assertEqual(ticket, "UT-000002")

        request = core.get_request(ticket, identity=student)

        self.assertIsNotNone(request)
        self.assertEqual(
            request["student_id"],
            "2024-1001",
        )
        self.assertEqual(
            request["request_type"],
            "Récord académico",
        )
        self.assertEqual(
            request["status"],
            "Recibida",
        )

    def test_create_request_direct_call_by_other_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1002",
            role="student",
        )

        with self.assertRaises(PermissionError):
            core.create_request(
                "2024-1001",
                "Récord académico",
                "Recibida",
                "Intento de registro para otra matrícula",
                identity=student,
            )

        admin = Identity(role="admin")
        requests = core.list_requests(identity=admin)

        # Solo debe existir la solicitud inicial de demostración.
        self.assertEqual(len(requests), 1)

    def test_create_request_direct_call_without_identity(self):
        from security import Identity

        with self.assertRaises(PermissionError):
            core.create_request(
                "2024-1001",
                "Récord académico",
                "Recibida",
                "Intento de registro sin autorización",
            )

        admin = Identity(role="admin")
        requests = core.list_requests(identity=admin)

        # Solo debe existir la solicitud inicial de demostración.
        self.assertEqual(len(requests), 1)

    def test_register_request_direct_call_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        response = core.register_request(
            "2024-1001",
            "Récord académico",
            identity=admin,
        )

        self.assertIn("UT-000002", response)

        request = core.get_request("UT-000002", identity=admin)

        self.assertIsNotNone(request)
        self.assertEqual(
            request["student_id"],
            "2024-1001",
        )
        self.assertEqual(
            request["request_type"],
            "Récord académico",
        )
        self.assertEqual(
            request["status"],
            "Recibida",
        )

    def test_register_request_direct_call_by_owner(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        response = core.register_request(
            "2024-1001",
            "Récord académico",
            identity=student,
        )

        self.assertIn("UT-000002", response)

        request = core.get_request("UT-000002", identity=student)

        self.assertIsNotNone(request)
        self.assertEqual(
            request["student_id"],
            "2024-1001",
        )
        self.assertEqual(
            request["request_type"],
            "Récord académico",
        )
        self.assertEqual(
            request["status"],
            "Recibida",
        )


    def test_register_request_direct_call_by_other_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1002",
            role="student",
        )

        response = core.register_request(
            "2024-1001",
            "Récord académico",
            identity=student,
        )

        self.assertIn(
            "Acceso denegado",
            response,
        )

        admin = Identity(role="admin")
        requests = core.list_requests(identity=admin)

        # No debe generarse una solicitud adicional.
        self.assertEqual(len(requests), 1)

    def test_register_request_direct_call_without_identity(self):
        from security import Identity

        response = core.register_request(
            "2024-1001",
            "Récord académico",
        )

        self.assertIn(
            "Acceso denegado",
            response,
        )

        admin = Identity(role="admin")
        requests = core.list_requests(identity=admin)

        # Solo debe existir la solicitud inicial de demostración.
        self.assertEqual(len(requests), 1)

    def test_authenticated_student_can_create_own_request(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        state = {
            "authenticated_identity": student,
        }

        core.handle_message(
            "Necesito un récord académico",
            state,
        )

        core.handle_message(
            "2024-1001",
            state,
        )

        response = core.handle_message(
            "confirmar",
            state,
        )

        self.assertIn(
            "UT-000002",
            response,
        )

        admin = Identity(role="admin")
        requests = core.list_requests(identity=admin)

        self.assertEqual(len(requests), 2)

        new_request = core.get_request("UT-000002", identity=admin)

        self.assertEqual(
            new_request["student_id"],
            "2024-1001",
        )

    def test_student_cannot_create_request_for_another_student(self):
        from security import Identity

        state = {
            "authenticated_identity": Identity(
                student_id="2024-1002",
                role="student",
            )
        }

        core.handle_message(
            "Necesito un récord académico",
            state,
        )

        response = core.handle_message(
            "2024-1001",
            state,
        )

        self.assertIsNone(state.get("pending_student"))
        self.assertFalse(state.get("pending_confirmation", False))

        self.assertIn(
            "Acceso denegado",
            response,
        )

        admin = Identity(role="admin")
        requests = core.list_requests(identity=admin)

        # Solo debe existir la solicitud inicial de demostración.
        self.assertEqual(len(requests), 1)


    def test_unauthenticated_user_cannot_create_request(self):
        state = {}

        core.handle_message(
            "Necesito un récord académico",
            state,
        )

        response = core.handle_message(
            "2024-1001",
            state,
        )

        self.assertIsNone(state.get("pending_student"))
        self.assertFalse(state.get("pending_confirmation", False))

        self.assertIn(
            "autenticación",
            response.lower(),
        )

        from security import Identity

        admin = Identity(role="admin")

        requests = core.list_requests(identity=admin)

        self.assertEqual(
            len(requests),
            1,
        )


    def test_ticket_history_without_identity(self):
        history = core.get_ticket_history("UT-000001")
        self.assertEqual(history, [])

    def test_ticket_history_by_other_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-9999",
            role="student",
        )

        history = core.get_ticket_history(
            "UT-000001",
            identity=student,
        )

        self.assertEqual(history, [])

    def test_ticket_history_by_owner(self):
        from security import Identity

        owner = Identity(
            student_id="2024-1001",
            role="student",
        )

        history = core.get_ticket_history(
            "UT-000001",
            identity=owner,
        )

        self.assertIsInstance(history, list)

    def test_ticket_history_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        history = core.get_ticket_history(
            "UT-000001",
            identity=admin,
        )

        self.assertIsInstance(history, list)



    def test_update_document_without_identity(self):
        result = core.update_document_status(
            "999999",
            "Aprobado",
            "Revisión de prueba",
        )

        self.assertIn("Acceso denegado", result)

    def test_update_document_by_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        result = core.update_document_status(
            "999999",
            "Aprobado",
            "Revisión de prueba",
            identity=student,
        )

        self.assertIn("Acceso denegado", result)


    def test_register_document_without_identity(self):
        result = core.register_document(
            "UT-000001",
            "requisito_prueba",
            "documento.pdf",
        )

        self.assertIn("Acceso denegado", result)

        from security import Identity

        admin = Identity(role="admin")

        documents = core.list_documents(
            "UT-000001",
            identity=admin,
        )

        self.assertFalse(
            any(
                doc["Documento"] == "documento.pdf"
                for doc in documents
            )
        )

    def test_register_document_by_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        result = core.register_document(
            "UT-000001",
            "requisito_prueba",
            "documento_estudiante.pdf",
            identity=student,
        )

        self.assertIn("Acceso denegado", result)

        admin = Identity(role="admin")

        documents = core.list_documents(
            "UT-000001",
            identity=admin,
        )

        self.assertFalse(
            any(
                doc["Documento"] == "documento_estudiante.pdf"
                for doc in documents
            )
        )



    def test_list_documents_without_identity(self):
        result = core.list_documents("UT-000001")
        self.assertEqual(result, [])

    def test_list_documents_by_other_student(self):
        from security import Identity

        student = Identity(
            student_id="2025-9999",
            role="student",
        )

        result = core.list_documents(
            "UT-000001",
            identity=student,
        )

        self.assertEqual(result, [])

    def test_list_documents_by_owner(self):
        from security import Identity


        owner = Identity(
            student_id="2024-1001",
            role="student",
        )

        request = core.get_request(
            "UT-000001",
            identity=owner,
        )
        self.assertIsNotNone(request)

        result = core.list_documents(
            "UT-000001",
            identity=owner,
        )

        self.assertIsInstance(result, list)

    def test_list_documents_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        result = core.list_documents(
            "UT-000001",
            identity=admin,
        )

        self.assertIsInstance(result, list)



    def test_list_requests_without_identity(self):
        result = core.list_requests()
        self.assertEqual(result, [])

    def test_list_requests_by_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        result = core.list_requests(identity=student)
        self.assertEqual(result, [])

    def test_list_requests_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        result = core.list_requests(identity=admin)

        self.assertIsInstance(result, list)
        self.assertTrue(
            any(r["Ticket"] == "UT-000001" for r in result)
        )


    def test_update_request_without_authorization(self):
        # Consultar el estado original
        from security import Identity

        admin = Identity(role="admin")
        # Consultar el estado original con identidad autorizada
        original = core.get_request("UT-000001", identity=admin)
        self.assertIsNotNone(original)

        original_status = original["status"]

        # Intentar modificar sin identidad administrativa
        result = core.update_request_status(
            "UT-000001",
            "Completada",
            "Intento de actualización no autorizado",
        )

        # Comprobar que el acceso fue rechazado
        self.assertIn("Acceso denegado", result)

        # Verificar que la base de datos no cambió
        updated = core.get_request("UT-000001", identity=admin)

        self.assertEqual(
            updated["status"],
            original_status,
        )

    def test_update_request_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        result = core.update_request_status(
            "UT-000001",
            "Completada",
            "Actualización administrativa de prueba",
            identity=admin,
        )

        # La función devuelve None cuando tiene éxito
        self.assertIsNone(result)

        updated = core.get_request("UT-000001", identity=admin)

        self.assertEqual(
            updated["status"],
            "Completada",
        )


    def test_change_request_type_before_confirmation(self):

        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )

        core.handle_message(
            "Necesito un récord académico",
            self.state
        )

        core.handle_message("2024-1001", self.state)

        self.assertEqual(self.saved(), [])

        reply = core.handle_message(
            "Quiero cambiar a certificación de estudio",
            self.state
        )

        self.assertIn("Certificación de estudio", reply)
        self.assertEqual(self.saved(), [])

        reply = core.handle_message("confirmar", self.state)

        self.assertIn("UT-", reply)
        self.assertEqual(len(self.saved()), 1)
        self.assertEqual(
            self.saved()[0]["Trámite"],
            "Certificación de estudio"
        )

    def test_cancel_before_student_id(self):
        core.handle_message(
            "Necesito un récord académico",
            self.state
        )

        reply = core.handle_message("cancelar", self.state)

        self.assertIn("cancelada", reply)
        self.assertEqual(self.saved(), [])
        self.assertIsNone(self.state["pending_type"])
        self.assertIsNone(self.state["pending_student"])

    def tearDown(self):
        core.DB_PATH = self.original_db
        self.tmp.cleanup()
        if self.original_url:
            os.environ["DATABASE_URL"] = self.original_url


    def saved(self):
        from security import Identity

        admin = Identity(role="admin")

        return [
            r
            for r in core.list_requests(identity=admin)
            if r["Ticket"] != "UT-000001"
        ]


    def test_type_then_student_id(self):

        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )
        core.handle_message("Necesito un récord académico", self.state)
        reply = core.handle_message("2024-1001", self.state)

        self.assertIn("confirmar", reply)
        self.assertEqual(self.saved(), [])

        reply = core.handle_message("confirmar", self.state)

        self.assertIn("UT-000002", reply)
        self.assertEqual(self.saved()[0]["Estado"], "Recibida")

    def test_type_and_student_id_in_same_message(self):

        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1002",
            role="student",
        )

        reply = core.handle_message(
            "Necesito un récord académico, mi matrícula es 2024-1002",
            self.state
        )

        self.assertIn("confirmar", reply)
        self.assertEqual(self.saved(), [])

        core.handle_message("confirmar", self.state)

        rows = self.saved()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Matrícula"], "2024-1002")
        self.assertEqual(rows[0]["Estado"], "Pendiente de revisión")

    def test_student_id_then_type(self):

        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )

        core.handle_message("2024-1001", self.state)
        reply = core.handle_message("certificación de estudio", self.state)

        self.assertIn("confirmar", reply)
        self.assertEqual(self.saved(), [])

        core.handle_message("confirmar", self.state)

        self.assertEqual(
            self.saved()[0]["Trámite"],
            "Certificación de estudio"
        )

    def test_student_id_with_status_keyword(self):

        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )

        core.handle_message(
            "Quiero una certificación de estudio",
            self.state
        )

        reply = core.handle_message(
            "mi matrícula es 2024-1001 para la solicitud",
            self.state
        )

        self.assertIn("confirmar", reply)
        self.assertEqual(self.saved(), [])

        core.handle_message("confirmar", self.state)

        self.assertEqual(len(self.saved()), 1)

    def test_unknown_student_is_not_saved(self):
        reply = core.handle_message(
            "récord para 9999-0000",
            self.state,
        )

        self.assertIn(
            "autenticación",
            reply.lower(),
        )

        self.assertNotIn(
            "no está registrada",
            reply.lower(),
        )

        self.assertIsNone(
            self.state.get("pending_student")
        )

        self.assertFalse(
            self.state.get("pending_confirmation", False)
        )

        self.assertEqual(self.saved(), [])

    def test_registered_student_can_request(self):
        from security import Identity

        admin = Identity(role="admin")

        self.assertIsNone(
            core.register_student(
                "2025-0001",
                "Prueba Nueva",
                True,
                False,
                identity=admin,
            )
        )

        self.state["authenticated_identity"] = Identity(
            student_id="2025-0001",
            role="student",
        )


        reply = core.handle_message(
            "récord académico 2025-0001",
            self.state
        )

        self.assertIn("confirmar", reply)
        self.assertEqual(self.saved(), [])

        core.handle_message("confirmar", self.state)

        rows = self.saved()
        self.assertEqual(rows[0]["Matrícula"], "2025-0001")
        self.assertEqual(rows[0]["Estado"], "Pendiente de revisión")


    def test_register_student_rejects_bad_input(self):
        from security import Identity

        admin = Identity(role="admin")

        self.assertIn(
            "formato",
            core.register_student(
                "2025", "X", True, True, identity=admin
            ),
        )

        self.assertIn(
            "obligatorio",
            core.register_student(
                "2025-0002", " ", True, True, identity=admin
            ),
        )

        self.assertIn(
            "ya está registrada",
            core.register_student(
                "2024-1001", "Otra", True, True, identity=admin
            ),
        )

        self.assertEqual(
            len(core.list_students(identity=admin)),
            3,
        )



    def test_cancel_request(self):
        core.handle_message(
            "Necesito un récord académico",
            self.state
        )

        core.handle_message("2024-1001", self.state)

        reply = core.handle_message("cancelar", self.state)

        self.assertIn("cancelada", reply)
        self.assertEqual(self.saved(), [])
        self.assertIsNone(self.state["pending_type"])
        self.assertIsNone(self.state["pending_student"])
        self.assertFalse(self.state["pending_confirmation"])

    def test_confirmation_required(self):

        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )

        reply = core.handle_message(
            "récord académico 2024-1001",
            self.state
        )

        self.assertIn("confirmar", reply)
        self.assertEqual(self.saved(), [])

        core.handle_message("confirmar", self.state)

        self.assertEqual(len(self.saved()), 1)

    def test_unrelated_message_does_not_register_request(self):
        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )
        core.handle_message(
            "récord académico 2024-1001",
            self.state
        )

        reply = core.handle_message(
            "Tengo otra pregunta",
            self.state
        )

        self.assertEqual(self.saved(), [])
        self.assertIn("confirmar", reply)


    def test_ticket_lookup_without_authentication(self):
        reply = core.handle_message(
            "estado de UT-000001",
            self.state,
        )

        self.assertIn("identidad verificada", reply)
        self.assertNotIn("En proceso", reply)

    def test_ticket_lookup_by_owner(self):
        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1001",
            role="student",
        )

        reply = core.handle_message(
            "estado de UT-000001",
            self.state,
        )

        self.assertIn("UT-000001", reply)
        self.assertIn("En proceso", reply)

    def test_ticket_lookup_by_other_student(self):
        from security import Identity

        self.state["authenticated_identity"] = Identity(
            student_id="2024-1002",
            role="student",
        )

        reply = core.handle_message(
            "estado de UT-000001",
            self.state,
        )

        self.assertIn("No se puede mostrar", reply)
        self.assertNotIn("En proceso", reply)

    def test_ticket_lookup_by_admin(self):
        from security import Identity

        self.state["authenticated_identity"] = Identity(
            role="admin",
        )

        reply = core.handle_message(
            "estado de UT-000001",
            self.state,
        )

        self.assertIn("UT-000001", reply)
        self.assertIn("En proceso", reply)


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "define TEST_DATABASE_URL para probar con PostgreSQL")
class TestChatSavesRequestsPostgres(TestChatSavesRequests):
    """Same scenarios on PostgreSQL. WARNING: drops the requests and students tables of TEST_DATABASE_URL."""
    def setUp(self):
        self.original_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
        core.run("DROP TABLE IF EXISTS requests")
        core.run("DROP TABLE IF EXISTS students")
        core.run("DROP SEQUENCE IF EXISTS request_number_seq")
        core.init_db()
        self.state = {"pending_type": None, "pending_student": None}



    def test_document_lifecycle_with_authorization(self):
        from security import Identity

        admin = Identity(role="admin")
        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        ticket = "UT-000001"
        file_name = "prueba_integracion_documento.pdf"

        # 1. Registrar documento como administrador.
        result = core.register_document(
            ticket,
            "matricula_activa",
            file_name,
            identity=admin,
        )

        self.assertIsNone(result)

        # 2. Localizar el documento registrado.
        documents = core.list_documents(
            ticket,
            identity=admin,
        )

        document = next(
            doc for doc in documents
            if doc["Documento"] == file_name
        )

        document_id = document["ID"]

        self.assertEqual(document["Estado"], "Pendiente")

        # 3. Aprobar el documento como administrador.
        result = core.update_document_status(
            document_id,
            "Aprobado",
            "Documento verificado correctamente",
            identity=admin,
        )

        self.assertIsNone(result)

        # 4. Intentar rechazarlo como estudiante.
        result = core.update_document_status(
            document_id,
            "Rechazado",
            "Intento no autorizado",
            identity=student,
        )

        self.assertIn("Acceso denegado", result)

        # 5. Comprobar que sigue aprobado.
        documents = core.list_documents(
            ticket,
            identity=admin,
        )

        updated_document = next(
            doc for doc in documents
            if doc["ID"] == document_id
        )

        self.assertEqual(
            updated_document["Estado"],
            "Aprobado",
        )


    def test_register_student_without_identity(self):
        result = core.register_student(
            "2025-0098",
            "Estudiante No Autorizado",
            True,
            True,
        )

        self.assertIn("Acceso denegado", result)
        from security import Identity

        admin = Identity(role="admin")

        self.assertIsNone(
            core.get_student("2025-0098", identity=admin)
        )

    def test_register_student_by_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        result = core.register_student(
            "2025-0099",
            "Estudiante No Autorizado",
            True,
            True,
            identity=student,
        )

        self.assertIn("Acceso denegado", result)
        admin = Identity(role="admin")

        self.assertIsNone(
            core.get_student("2025-0099", identity=admin)
        )


    def test_list_students_without_identity(self):
        result = core.list_students()
        self.assertEqual(result, [])

    def test_list_students_by_student(self):
        from security import Identity

        student = Identity(
            student_id="2024-1001",
            role="student",
        )

        result = core.list_students(identity=student)

        self.assertEqual(result, [])

    def test_list_students_by_admin(self):
        from security import Identity

        admin = Identity(role="admin")

        result = core.list_students(identity=admin)

        self.assertIsInstance(result, list)
        self.assertTrue(
            any(
                student["Matrícula"] == "2024-1001"
                for student in result
            )
        )


    def tearDown(self):
        if self.original_url:
            os.environ["DATABASE_URL"] = self.original_url
        else:
            os.environ.pop("DATABASE_URL", None)

if __name__ == "__main__":
    unittest.main()
