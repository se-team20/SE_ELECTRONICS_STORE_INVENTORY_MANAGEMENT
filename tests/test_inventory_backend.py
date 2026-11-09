        self.assertIn(b"SKU already exists", response.data)

    def test_negative_quantity_is_rejected(self):
        response = self.client.post(
            "/add",
            data=self.payload(quantity="-1"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.get_component("CAP-001"))

    def test_fractional_quantity_is_rejected(self):
        response = self.client.post(
            "/add",
            data=self.payload(quantity="1.5"),
        )

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
            "/add",
            data=self.payload(min_stock_level="-2"),
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

        response = self.client.post(
            f"/delete/{row['component_id']}",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.get_component("CAP-001"))

    def test_component_minimum_stock_level_controls_status(self):
        self.assertEqual(
            inventory_app.get_status(0, 5),
            "Out of Stock",
        )
        self.assertEqual(
            inventory_app.get_status(5, 5),
            "Low Stock",
        )
        self.assertEqual(
            inventory_app.get_status(6, 5),
            "Available",
        )

    def test_configurable_default_low_stock_threshold(self):
        self.assertEqual(
            inventory_app.get_status(5),
            "Low Stock",
        )
        self.assertEqual(
            inventory_app.get_status(6),
            "Available",
        )

    def test_sqlite_enforces_unique_sku(self):
        self.client.post("/add", data=self.payload())

        conn = inventory_app.get_db_connection()
        try:
            with self.assertRaises(Exception):
                conn.execute(
                    """
                    INSERT INTO components
                    (sku, component_name, category, quantity, price)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("CAP-001", "Duplicate", "Passive", 1, 1.0),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
