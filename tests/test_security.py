
import unittest

from security import (
    Identity,
    can_view_request,
    can_manage_requests,
    can_manage_students,
    can_manage_documents,
)


class TestSecurity(unittest.TestCase):

    def setUp(self):
        self.request = {
            "ticket": "UT-000001",
            "student_id": "2024-1001",
            "status": "En proceso",
        }


    def test_anonymous_cannot_manage_documents(self):
        identity = Identity()

        self.assertFalse(
            can_manage_documents(identity)
        )

    def test_student_cannot_manage_documents(self):
        identity = Identity(
            student_id="2024-1001",
            role="student",
        )

        self.assertFalse(
            can_manage_documents(identity)
        )

    def test_admin_can_manage_documents(self):
        identity = Identity(role="admin")

        self.assertTrue(
            can_manage_documents(identity)
        )

    def test_missing_identity_cannot_manage_documents(self):
        self.assertFalse(
            can_manage_documents(None)
        )

    def test_anonymous_cannot_view_request(self):
        identity = Identity()

        self.assertFalse(
            can_view_request(identity, self.request)
        )

    def test_owner_can_view_request(self):
        identity = Identity(
            student_id="2024-1001",
            role="student",
        )

        self.assertTrue(
            can_view_request(identity, self.request)
        )

    def test_other_student_cannot_view_request(self):
        identity = Identity(
            student_id="2024-1002",
            role="student",
        )

        self.assertFalse(
            can_view_request(identity, self.request)
        )

    def test_admin_can_view_request(self):
        identity = Identity(role="admin")

        self.assertTrue(
            can_view_request(identity, self.request)
        )

    def test_missing_identity_is_denied(self):
        self.assertFalse(
            can_view_request(None, self.request)
        )

    def test_missing_request_is_denied(self):
        identity = Identity(role="admin")

        self.assertFalse(
            can_view_request(identity, None)
        )

    def test_student_cannot_manage_requests(self):
        identity = Identity(
            student_id="2024-1001",
            role="student",
        )

        self.assertFalse(
            can_manage_requests(identity)
        )

    def test_admin_can_manage_requests(self):
        identity = Identity(role="admin")

        self.assertTrue(
            can_manage_requests(identity)
        )

    def test_student_cannot_manage_students(self):
        identity = Identity(
            student_id="2024-1001",
            role="student",
        )

        self.assertFalse(
            can_manage_students(identity)
        )

    def test_admin_can_manage_students(self):
        identity = Identity(role="admin")

        self.assertTrue(
            can_manage_students(identity)
        )


if __name__ == "__main__":
    unittest.main()
