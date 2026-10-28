
import os
import tempfile
import unittest

import app as inventory_app


class FrontendIntegrationTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)

        self.old_database = inventory_app.app.config["DATABASE"]
        inventory_app.app.config["DATABASE"] = self.db_path
        inventory_app.app.config["TESTING"] = True

        inventory_app.initialize_database()
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        inventory_app.app.config["DATABASE"] = self.old_database
        inventory_app.app.config["TESTING"] = self.old_testing
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def add_sample_component(self, name="Arduino", category="Boards",
                             quantity=15, price=20.0):
        conn = inventory_app.get_db_connection()
        cursor = conn.execute(
            """
           INSERT INTO components
           (sku, component_name, category, quantity, price)
           VALUES (?, ?, ?, ?, ?)
            """,
            (f"TEST-{name.replace(' ', '-')}", name, category, quantity, price)
        )
        conn.commit()
        component_id = cursor.lastrowid
        conn.close()
        return component_id

    def test_dashboard_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Inventory Dashboard", response.data)

    def test_inventory_renders(self):
        self.add_sample_component()
        response = self.client.get("/inventory")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Arduino", response.data)

    def test_add_form_renders(self):
        response = self.client.get("/add")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"component_name", response.data)

    def test_report_renders(self):
        response = self.client.get("/report")
        self.assertEqual(response.status_code, 200)

    def test_valid_submission_adds_component(self):
        response = self.client.post("/add", data={
            "sku": "TEST-ARDUINO",
            "component_name": "Arduino",
            "category": "Boards",
            "quantity": "15",
            "price": "20.50",
        })
        self.assertEqual(response.status_code, 302)

        conn = inventory_app.get_db_connection()
        row = conn.execute(
            "SELECT * FROM components WHERE component_name = ?",
            ("Arduino",),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["quantity"], 15)

    def test_invalid_submission_returns_error(self):
        response = self.client.post("/add", data={
            "component_name": "",
            "category": "",
            "quantity": "-1",
            "price": "invalid",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Component name is required", response.data)
        self.assertIn(b"Price must be a valid number", response.data)

    def test_search_filters_inventory(self):
        self.add_sample_component("Arduino")
        self.add_sample_component("Resistor", "Passive", 50, 1.0)

        response = self.client.get("/inventory?search=Arduino")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Arduino", response.data)
        self.assertNotIn(b"Resistor", response.data)

    def test_category_filter(self):
        self.add_sample_component("Arduino", "Boards")
        self.add_sample_component("Resistor", "Passive", 50, 1.0)

        response = self.client.get("/inventory?category=Passive")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Resistor", response.data)
        self.assertNotIn(b"Arduino", response.data)

    def test_status_filter(self):
        self.add_sample_component("Arduino", "Boards", 15)
        self.add_sample_component("Low stock resistor", "Passive", 5, 1.0)

        response = self.client.get("/inventory?status=Low+Stock")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Low stock resistor", response.data)
        self.assertNotIn(b"Arduino", response.data)

    def test_edit_component(self):
        component_id = self.add_sample_component()
        response = self.client.post(
            f"/edit/{component_id}",
            data={
                "sku": "TEST-ARDUINO-UPDATED",
                "component_name": "Updated Arduino",
                "category": "Boards",
                "quantity": "20",
                "price": "25.0",
            },
        )
        self.assertEqual(response.status_code, 302)

        conn = inventory_app.get_db_connection()
        row = conn.execute(
            "SELECT * FROM components WHERE component_id = ?",
            (component_id,),
        ).fetchone()
        conn.close()

        self.assertEqual(row["component_name"], "Updated Arduino")
        self.assertEqual(row["quantity"], 20)

    def test_missing_component_edit_redirects(self):
        response = self.client.get("/edit/99999")
        self.assertEqual(response.status_code, 302)

    def test_delete_component(self):
        component_id = self.add_sample_component()
        response = self.client.post(f"/delete/{component_id}")
        self.assertEqual(response.status_code, 302)

        conn = inventory_app.get_db_connection()
        row = conn.execute(
            "SELECT * FROM components WHERE component_id = ?",
            (component_id,),
        ).fetchone()
        conn.close()

        self.assertIsNone(row)

    def test_delete_get_is_not_allowed(self):
        response = self.client.get("/delete/1")
        self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main()

