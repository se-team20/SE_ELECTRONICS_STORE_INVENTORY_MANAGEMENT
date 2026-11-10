
import os
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-for-ci")

import app as inventory_app
from unittest.mock import patch


class AuditLoggingTests(unittest.TestCase):

    def test_add_component_rolls_back_when_audit_logging_fails(self):
        with patch.object(
            inventory_app,
            "log_action",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.add_component()

        conn = inventory_app.get_db_connection()
        try:
            component = conn.execute(
                "SELECT * FROM components WHERE sku = ?",
                ("AUDIT-001",),
            ).fetchone()

            logs = conn.execute(
                "SELECT * FROM audit_logs"
            ).fetchall()
        finally:
            conn.close()

        self.assertIsNone(component)
        self.assertEqual(len(logs), 0)


    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)

        self.old_database = inventory_app.app.config["DATABASE"]
        self.old_testing = inventory_app.app.config["TESTING"]

        inventory_app.app.config["DATABASE"] = self.db_path
        inventory_app.app.config["TESTING"] = True

        inventory_app.initialize_database()

        inventory_app.create_user(
            "audituser",
            "TestPassword123!",
            role="Store Manager"
        )

        self.client = inventory_app.app.test_client()

        self.client.post(
            "/login",
            data={
                "username": "audituser",
                "password": "TestPassword123!"
            }
        )

    def tearDown(self):
        inventory_app.app.config["DATABASE"] = self.old_database
        inventory_app.app.config["TESTING"] = self.old_testing

        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def get_audit_logs(self):
        conn = inventory_app.get_db_connection()
        try:
            return conn.execute(
                "SELECT * FROM audit_logs ORDER BY log_id"
            ).fetchall()
        finally:
            conn.close()

    def add_component(self):
        return self.client.post(
            "/add",
            data={
                "sku": "AUDIT-001",
                "component_name": "Arduino",
                "category": "Boards",
                "quantity": "20",
                "price": "500",
                "min_stock_level": "5"
            }
        )

    def get_component_id(self):
        conn = inventory_app.get_db_connection()
        try:
            row = conn.execute(
                "SELECT component_id FROM components WHERE sku = ?",
                ("AUDIT-001",)
            ).fetchone()
            return row["component_id"]
        finally:
            conn.close()

    def test_add_component_creates_audit_record(self):
        response = self.add_component()
        self.assertEqual(response.status_code, 302)

        logs = self.get_audit_logs()

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["username"], "audituser")
        self.assertEqual(logs[0]["action"], "ADD_COMPONENT")
        self.assertEqual(
            logs[0]["component_id"],
            self.get_component_id()
        )
        self.assertTrue(logs[0]["timestamp"])

    def test_edit_component_creates_audit_record(self):
        self.add_component()
        component_id = self.get_component_id()

        response = self.client.post(
            f"/edit/{component_id}",
            data={
                "sku": "AUDIT-001",
                "component_name": "Updated Arduino",
                "category": "Boards",
                "quantity": "25",
                "price": "550",
                "min_stock_level": "5"
            }
        )

        self.assertEqual(response.status_code, 302)

        logs = self.get_audit_logs()

        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[1]["username"], "audituser")
        self.assertEqual(logs[1]["action"], "EDIT_COMPONENT")
        self.assertEqual(logs[1]["component_id"], component_id)
        self.assertTrue(logs[1]["timestamp"])

    def test_delete_component_creates_audit_record(self):
        self.add_component()
        component_id = self.get_component_id()

        response = self.client.post(
            f"/delete/{component_id}"
        )

        self.assertEqual(response.status_code, 302)

        logs = self.get_audit_logs()

        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[1]["username"], "audituser")
        self.assertEqual(logs[1]["action"], "DELETE_COMPONENT")
        self.assertEqual(logs[1]["component_id"], component_id)
        self.assertTrue(logs[1]["timestamp"])

    def test_audit_records_contain_authenticated_user_id(self):
        self.add_component()

        logs = self.get_audit_logs()

        with self.client.session_transaction() as session:
            logged_in_user_id = session["user_id"]

        self.assertEqual(logs[0]["user_id"], logged_in_user_id)


if __name__ == "__main__":
    unittest.main()
