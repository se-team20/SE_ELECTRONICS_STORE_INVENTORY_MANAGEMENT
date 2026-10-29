import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import pytest

import app as inventory_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create an isolated test database for each test."""
    test_db = tmp_path / "test_inventory.db"

    monkeypatch.setitem(
        inventory_app.app.config, "DATABASE", str(test_db)
    )
    inventory_app.app.config["TESTING"] = True
    inventory_app.initialize_database()

    with inventory_app.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["_user_id"] = "1"
            session["user_id"] = 1
        yield test_client


def add_component(client, name="Keyboard", category="Accessories",
                  quantity=15, price=799.0):
    return client.post("/add", data={
        "sku": f"TEST-{name.replace(' ', '-').upper()}",
        "component_name": name,
        "category": category,
        "quantity": str(quantity),
        "price": str(price),
        "min_stock_level": "10",
    }, follow_redirects=False)


def test_stock_status_boundaries():
    assert inventory_app.get_status(0) == "Out of Stock"
    assert inventory_app.get_status(1) == "Low Stock"
    assert inventory_app.get_status(10) == "Low Stock"
    assert inventory_app.get_status(11) == "Available"


def test_add_component_saves_to_database(client):
    response = add_component(client, "Keyboard", quantity=15)
    assert response.status_code == 302

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    row = conn.execute(
        "SELECT component_name, category, quantity, price FROM components"
    ).fetchone()
    conn.close()

    assert row == ("Keyboard", "Accessories", 15, 799.0)


def test_delete_component(client):
    add_component(client, "Keyboard", quantity=15)

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    component_id = conn.execute(
        "SELECT component_id FROM components"
    ).fetchone()[0]
    conn.close()

    response = client.post(f"/delete/{component_id}")
    assert response.status_code in (302, 303)

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    remaining = conn.execute(
        "SELECT COUNT(*) FROM components"
    ).fetchone()[0]
    conn.close()

    assert remaining == 0


def test_stock_status_counts():
    quantities = [15, 20, 5, 10, 0, 0]

    available = sum(
        1 for q in quantities
        if inventory_app.get_status(q) == "Available"
    )
    low_stock = sum(
        1 for q in quantities
        if inventory_app.get_status(q) == "Low Stock"
    )
    out_of_stock = sum(
        1 for q in quantities
        if inventory_app.get_status(q) == "Out of Stock"
    )

    assert available == 2
    assert low_stock == 2
    assert out_of_stock == 2


def test_dashboard_calculations(client):
    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    conn.executemany(
        """
        INSERT INTO components
        (sku, component_name, category, quantity, price, min_stock_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("DASH-1", "Keyboard", "Accessories", 15, 799.0, 10),
            ("DASH-2", "Mouse", "Accessories", 5, 299.0, 10),
            ("DASH-3", "Monitor", "Displays", 0, 8999.0, 10),
            ("DASH-4", "Cable", "Accessories", 10, 199.0, 10),
        ],
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    components = conn.execute(
        "SELECT quantity FROM components"
    ).fetchall()
    conn.close()

    quantities = [row[0] for row in components]

    assert len(quantities) == 4
    assert sum(inventory_app.get_status(q) == "Available" for q in quantities) == 1
    assert sum(inventory_app.get_status(q) == "Low Stock" for q in quantities) == 2
    assert sum(inventory_app.get_status(q) == "Out of Stock" for q in quantities) == 1


def test_report_categorizes_components(client):
    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    conn.executemany(
        """
        INSERT INTO components
        (sku, component_name, category, quantity, price, min_stock_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("REPORT-1", "Keyboard", "Accessories", 15, 799.0, 10),
            ("REPORT-2", "Mouse", "Accessories", 5, 299.0, 10),
            ("REPORT-3", "Monitor", "Displays", 0, 8999.0, 10),
        ],
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    quantities = conn.execute(
        "SELECT quantity FROM components"
    ).fetchall()
    conn.close()

    statuses = [inventory_app.get_status(row[0]) for row in quantities]

    assert statuses.count("Available") == 1
    assert statuses.count("Low Stock") == 1
    assert statuses.count("Out of Stock") == 1


def test_add_component_rejects_invalid_quantity(client):
    response = add_component(
        client, name="Invalid Keyboard", quantity="abc", price=799.0
    )

    assert response.status_code == 400

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    count = conn.execute(
        "SELECT COUNT(*) FROM components"
    ).fetchone()[0]
    conn.close()

    assert count == 0


def test_add_component_rejects_invalid_price(client):
    response = add_component(
        client, name="Invalid Mouse", quantity=5, price="invalid"
    )

    assert response.status_code == 400

    conn = sqlite3.connect(inventory_app.app.config["DATABASE"])
    count = conn.execute(
        "SELECT COUNT(*) FROM components"
    ).fetchone()[0]
    conn.close()

    assert count == 0
