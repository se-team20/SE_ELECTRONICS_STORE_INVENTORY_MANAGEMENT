
import os
import sqlite3

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "dev-only-change-this-before-deployment"
)
app.config["DATABASE"] = os.environ.get("DATABASE", "database.db")


def get_db_connection():
    conn = sqlite3.connect(app.config["DATABASE"])
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
    if quantity <= 10:
        return "Low Stock"
    return "Available"


def validate_component(form):
    name = form.get("component_name", "").strip()
    category = form.get("category", "").strip()
    quantity_text = form.get("quantity", "").strip()
    price_text = form.get("price", "").strip()

    errors = []

    if not name:
        errors.append("Component name is required.")
    if not category:
        errors.append("Category is required.")

    quantity = None
    try:
        quantity = int(quantity_text)
        if quantity < 0:
            errors.append("Quantity cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Quantity must be a whole number.")

    price = None
    try:
        price = float(price_text)
        if not 0 <= price < float("inf"):
            errors.append("Price must be a non-negative number.")
    except (ValueError, TypeError):
        errors.append("Price must be a valid number.")

    if errors:
        return None, errors

    return {
        "component_name": name,
        "category": category,
        "quantity": quantity,
        "price": price,
    }, []


@app.route("/")
def dashboard():
    conn = get_db_connection()
    components = conn.execute(
        "SELECT * FROM components"
    ).fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        total=len(components),
        available=sum(
            get_status(c["quantity"]) == "Available"
            for c in components
        ),
        low_stock=sum(
            get_status(c["quantity"]) == "Low Stock"
            for c in components
        ),
        out_of_stock=sum(
            get_status(c["quantity"]) == "Out of Stock"
            for c in components
        ),
    )


@app.route("/inventory")
def inventory():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db_connection()
    components = conn.execute(
        "SELECT * FROM components ORDER BY component_id"
    ).fetchall()
    conn.close()

    filtered = []
    for component in components:
        if search and search.casefold() not in component[
            "component_name"
        ].casefold():
            continue
        if category and component["category"] != category:
            continue
        if status and get_status(component["quantity"]) != status:
            continue
        filtered.append(component)

    categories = sorted({c["category"] for c in components})

    return render_template(
        "inventory.html",
        components=filtered,
        categories=categories,
        search=search,
        selected_category=category,
        selected_status=status,
        get_status=get_status,
    )


@app.route("/add", methods=["GET", "POST"])
def add_component():
    if request.method == "POST":
        data, errors = validate_component(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_component.html"), 400

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO components
                (component_name, category, quantity, price)
            VALUES (?, ?, ?, ?)
            """,
            (
                data["component_name"],
                data["category"],
                data["quantity"],
                data["price"],
            ),
        )
        conn.commit()
        conn.close()

        flash("Component added successfully.", "success")
        return redirect(url_for("inventory"))

    return render_template("add_component.html")


@app.route("/edit/<int:component_id>", methods=["GET", "POST"])
def edit_component(component_id):
    conn = get_db_connection()
    component = conn.execute(
        "SELECT * FROM components WHERE component_id = ?",
        (component_id,),
    ).fetchone()

    if component is None:
        conn.close()
        flash("Component not found.", "error")
        return redirect(url_for("inventory"))

    if request.method == "POST":
        data, errors = validate_component(request.form)
        if errors:
            conn.close()
            for error in errors:
                flash(error, "error")
            return render_template(
                "edit_component.html", component=component
            ), 400

        conn.execute(
            """
            UPDATE components
            SET component_name = ?, category = ?, quantity = ?, price = ?
            WHERE component_id = ?
            """,
            (
                data["component_name"],
                data["category"],
                data["quantity"],
                data["price"],
                component_id,
            ),
        )
        conn.commit()
        conn.close()

        flash("Component updated successfully.", "success")
        return redirect(url_for("inventory"))

    conn.close()
    return render_template("edit_component.html", component=component)


@app.route("/delete/<int:component_id>", methods=["POST"])
def delete_component(component_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM components WHERE component_id = ?",
        (component_id,),
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if deleted:
        flash("Component deleted successfully.", "success")
    else:
        flash("Component not found.", "error")

    return redirect(url_for("inventory"))


@app.route("/report")
def report():
    conn = get_db_connection()
    components = conn.execute(
        "SELECT * FROM components ORDER BY component_id"
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
        out_of_stock=out_of_stock,
    )


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
