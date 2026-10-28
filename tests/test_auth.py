
import os
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-for-ci")

import app as inventory_app


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)

        self.old_database = inventory_app.app.config["DATABASE"]
        self.old_testing = inventory_app.app.config["TESTING"]

        inventory_app.app.config["DATABASE"] = self.db_path
        inventory_app.app.config["TESTING"] = True

        inventory_app.initialize_database()
        inventory_app.create_user("testuser", "TestPassword123!")

        self.client = inventory_app.app.test_client()

    def tearDown(self):
        inventory_app.app.config["DATABASE"] = self.old_database
        inventory_app.app.config["TESTING"] = self.old_testing

        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def login(self, username="testuser", password="TestPassword123!"):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
        )

    def test_login_page_is_accessible(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)

    def test_valid_login_succeeds(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)

        with self.client.session_transaction() as session:
            self.assertIn("user_id", session)
            self.assertEqual(session["username"], "testuser")

    def test_invalid_password_is_rejected(self):
        response = self.login(password="WrongPassword123!")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password", response.data)

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_unknown_user_is_rejected(self):
        response = self.login(username="unknownuser")
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_password_is_stored_as_hash(self):
        conn = inventory_app.get_db_connection()
        try:
            user = conn.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                ("testuser",),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(user)
        self.assertNotEqual(user["password_hash"], "TestPassword123!")
        self.assertTrue(
            inventory_app.check_password_hash(
                user["password_hash"], "TestPassword123!"
            )
        )

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_inventory_requires_login(self):
        response = self.client.get("/inventory")
        self.assertEqual(response.status_code, 302)

    def test_add_requires_login(self):
        response = self.client.get("/add")
        self.assertEqual(response.status_code, 302)

    def test_edit_requires_login(self):
        response = self.client.get("/edit/1")
        self.assertEqual(response.status_code, 302)

    def test_report_requires_login(self):
        response = self.client.get("/report")
        self.assertEqual(response.status_code, 302)

    def test_delete_requires_login(self):
        response = self.client.post("/delete/1")
        self.assertEqual(response.status_code, 302)

    def test_logout_clears_session(self):
        self.login()

        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)
            self.assertNotIn("username", session)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_logout_requires_post(self):
        self.login()
        response = self.client.get("/logout")
        self.assertEqual(response.status_code, 405)

    def test_duplicate_username_is_rejected(self):
        with self.assertRaises(Exception):
            inventory_app.create_user("testuser", "AnotherPassword123!")


if __name__ == "__main__":
    unittest.main()
