import os
import tempfile
import unittest

import app as inventory_app


class InventoryBackendTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)

        self.old_database = inventory_app.app.config["DATABASE"]
        self.old_threshold = inventory_app.app.config["LOW_STOCK_THRESHOLD"]
        self.old_testing = inventory_app.app.config["TESTING"]

        inventory_app.app.config["DATABASE"] = self.db_path
        inventory_app.app.config["LOW_STOCK_THRESHOLD"] = 5
        inventory_app.app.config["TESTING"] = True

        inventory_app.initialize_database()
        self.client = inventory_app.app.test_client()

        # Authenticate the test client without disabling login protection.
        with self.client.session_transaction() as session:
            session["user_id"] = 1

    def tearDown(self):
        inventory_app.app.config["DATABASE"] = self.old_database
        inventory_app.app.config["LOW_STOCK_THRESHOLD"] = self.old_threshold
        inventory_app.app.config["TESTING"] = self.old_testing

        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                # Retry after garbage collection releases lingering connections.
                import gc
                gc.collect()
                try:
                    os.remove(self.db_path)
                except PermissionError:
                    pass

    def payload(self, **overrides):
        data = {
            "sku": "CAP-001",
            "component_name": "Capacitor",
            "category": "Passive",
            "quantity": "20",
            "price": "2.50",
            "min_stock_level": "5",
        }
        data.update(overrides)
        return data

    def get_component(self, sku):
        conn = inventory_app.get_db_connection()
        try:
            return conn.execute(
                "SELECT * FROM components WHERE sku = ?", (sku,)
            ).fetchone()
        finally:
            conn.close()

    def test_create_component_persists_all_fields(self):
        response = self.client.post("/add", data=self.payload())
        self.assertEqual(response.status_code, 302)
        row = self.get_component("CAP-001")
        self.assertIsNotNone(row)
        self.assertEqual(row["quantity"], 20)
        self.assertEqual(row["min_stock_level"], 5)

    def test_duplicate_sku_is_rejected_case_insensitively(self):
        self.client.post("/add", data=self.payload())
        response = self.client.post(
            "/add",
            data=self.payload(sku="cap-001", component_name="Other"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"SKU already exists", response.data)

    def test_negative_quantity_is_rejected(self):
        response = self.client.post("/add", data=self.payload(quantity="-1"))
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.get_component("CAP-001"))

    def test_fractional_quantity_is_rejected(self):
        response = self.client.post("/add", data=self.payload(quantity="1.5"))
        self.assertEqual(response.status_code, 400)

    def test_negative_and_non_finite_prices_are_rejected(self):
        for price in ("-1", "nan", "inf"):
            with self.subTest(price=price):
                response = self.client.post(
                    "/add",
                    data=self.payload(sku=f"CAP-{price}", price=price),
                )
                self.assertEqual(response.status_code, 400)

    def test_negative_minimum_stock_level_is_rejected(self):
        response = self.client.post(
            "/add", data=self.payload(min_stock_level="-2")
        )
        self.assertEqual(response.status_code, 400)

    def test_update_component_changes_fields(self):
        self.client.post("/add", data=self.payload())
        row = self.get_component("CAP-001")
        self.assertIsNotNone(row)

        response = self.client.post(
            f"/edit/{row['component_id']}",
            data=self.payload(
                sku="CAP-002",
                component_name="Updated capacitor",
                quantity="3",
                min_stock_level="4",
            ),
        )
        self.assertEqual(response.status_code, 302)

        updated = self.get_component("CAP-002")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["component_name"], "Updated capacitor")
        self.assertEqual(updated["quantity"], 3)
        self.assertEqual(updated["min_stock_level"], 4)

    def test_delete_component_removes_record(self):
        self.client.post("/add", data=self.payload())
        row = self.get_component("CAP-001")
        self.assertIsNotNone(row)

        response = self.client.post(f"/delete/{row['component_id']}")
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.get_component("CAP-001"))

    def test_component_minimum_stock_level_controls_status(self):
        self.assertEqual(inventory_app.get_status(0, 5), "Out of Stock")
        self.assertEqual(inventory_app.get_status(5, 5), "Low Stock")
        self.assertEqual(inventory_app.get_status(6, 5), "Available")

    def test_configurable_default_low_stock_threshold(self):
        self.assertEqual(inventory_app.get_status(5), "Low Stock")
        self.assertEqual(inventory_app.get_status(6), "Available")

    def test_sqlite_enforces_unique_sku(self):
        self.client.post("/add", data=self.payload())
        conn = inventory_app.get_db_connection()
        try:
            with self.assertRaises(Exception):
                conn.execute(
                    "INSERT INTO components "
                    "(sku, component_name, category, quantity, price) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("CAP-001", "Duplicate", "Passive", 1, 1.0),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()