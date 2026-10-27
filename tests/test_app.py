
import sqlite3
import pytest

import app as inventory_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create an isolated test database for each test."""
    test_db = tmp_path / "test_inventory.db"
    monkeypatch.setattr(inventory_app, "DATABASE", str(test_db))

    conn = sqlite3.connect(test_db)
    conn.execute("""
        CREATE TABLE components (
            component_id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    inventory_app.app.config["TESTING"] = True

    with inventory_app.app.test_client() as test_client:
        yield test_client


def add_component(client, name="Keyboard", category="Accessories",
                  quantity=15, price=799.0):
    return client.post("/add", data={
        "component_name": name,
        "category": category,
        "quantity": str(quantity),
        "price": str(price),
    }, follow_redirects=True)


def test_stock_status_boundaries():
    assert inventory_app.get_status(0) == "Out of Stock"
    assert inventory_app.get_status(1) == "Low Stock"
    assert inventory_app.get_status(10) == "Low Stock"
    assert inventory_app.get_status(11) == "Available"


def test_dashboard_counts_components(client):
    add_component(client, "Keyboard", quantity=15)
    add_component(client, "Mouse", quantity=5)
    add_component(client, "Monitor", quantity=0)

    response = client.get("/")

    assert response.status_code == 200
    assert b"dashboard.html" not in response.data
    assert b"Keyboard" not in response.data


def test_add_component_saves_to_database(client):
    response = add_component(client, "Keyboard", quantity=15)

    assert response.status_code == 200

    conn = sqlite3.connect(inventory_app.DATABASE)
    row = conn.execute(
        "SELECT component_name, category, quantity, price FROM components"
    ).fetchone()
    conn.close()

    assert row == ("Keyboard", "Accessories", 15, 799.0)


def test_inventory_page_loads(client):
    response = client.get("/inventory")
    assert response.status_code == 200


def test_report_page_loads(client):
    response = client.get("/report")
    assert response.status_code == 200


def test_delete_component(client):
    add_component(client, "Keyboard", quantity=15)

    conn = sqlite3.connect(inventory_app.DATABASE)
    component_id = conn.execute(
        "SELECT component_id FROM components"
    ).fetchone()[0]
    conn.close()

    response = client.get(f"/delete/{component_id}")
    assert response.status_code == 302

    conn = sqlite3.connect(inventory_app.DATABASE)
    remaining = conn.execute(
        "SELECT COUNT(*) FROM components"
    ).fetchone()[0]
    conn.close()

    assert remaining == 0
