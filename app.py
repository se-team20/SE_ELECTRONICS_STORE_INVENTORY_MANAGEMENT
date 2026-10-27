```python
from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

DATABASE = "database.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS components (
            component_id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_status(quantity):
    if quantity == 0:
        return "Out of Stock"
    elif quantity <= 10:
        return "Low Stock"
    else:
        return "Available"


@app.route("/")
def dashboard():
    conn = get_db_connection()
    components = conn.execute(
        "SELECT * FROM components"
    ).fetchall()
    conn.close()

    total = len(components)
    available = sum(
        1 for c in components
        if get_status(c["quantity"]) == "Available"
    )
    low_stock = sum(
        1 for c in components
        if get_status(c["quantity"]) == "Low Stock"
    )
    out_of_stock = sum(
        1 for c in components
        if get_status(c["quantity"]) == "Out of Stock"
    )

    return render_template(
        "dashboard.html",
        total=total,
        available=available,
        low_stock=low_stock,
        out_of_stock=out_of_stock
    )


@app.route("/inventory")
def inventory():
    conn = get_db_connection()
    components = conn.execute(
        "SELECT * FROM components"
    ).fetchall()
    conn.close()

    return render_template(
        "inventory.html",
        components=components,
        get_status=get_status
    )


@app.route("/add", methods=["GET", "POST"])
def add_component():
    if request.method == "POST":
        component_name = request.form.get(
            "component_name", ""
        ).strip()
        category = request.form.get(
            "category", ""
        ).strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            price = float(request.form.get("price", ""))
        except (ValueError, TypeError):
            return "Invalid quantity or price", 400

        if not component_name or not category:
            return "Component name and category are required", 400

        if quantity < 0 or price < 0:
            return "Quantity and price must not be negative", 400

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO components
                (component_name, category, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (
                component_name,
                category,
                quantity,
                price
            ))
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            return "Unable to save component", 500
        finally:
            conn.close()

        return redirect("/inventory")

    return render_template("add_component.html")


@app.route("/delete/<int:component_id>")
def delete_component(component_id):
    conn = get_db_connection()

    conn.execute(
        "DELETE FROM components WHERE component_id = ?",
        (component_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/inventory")


@app.route("/report")
def report():
    conn = get_db_connection()
    components = conn.execute(
        "SELECT * FROM components"
    ).fetchall()
    conn.close()

    available = []
    low_stock = []
    out_of_stock = []

    for component in components:
        status = get_status(component["quantity"])

        if status == "Available":
            available.append(component)
        elif status == "Low Stock":
            low_stock.append(component)
        else:
            out_of_stock.append(component)

    return render_template(
        "report.html",
        available=available,
        low_stock=low_stock,
        out_of_stock=out_of_stock
    )


if __name__ == "__main__":
    initialize_database()

    print("==========================================")
    print(" Electronics Store Inventory Management")
    print("==========================================")
    print("Server starting...")
    print("Open: http://127.0.0.1:5000")

    app.run(debug=True)
```
