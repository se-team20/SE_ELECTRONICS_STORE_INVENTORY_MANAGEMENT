import math
import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-before-deployment")
app.config["DATABASE"] = os.environ.get("DATABASE", "database.db")
app.config["LOW_STOCK_THRESHOLD"] = int(os.environ.get("LOW_STOCK_THRESHOLD", "10"))


def get_db_connection():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    """Create the inventory schema and migrate older databases safely."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS components (
            component_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL UNIQUE,
            component_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            price REAL NOT NULL CHECK (price >= 0),
            min_stock_level INTEGER NOT NULL DEFAULT 10 CHECK (min_stock_level >= 0)
        )
    """)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(components)")}
    if "sku" not in columns:
        conn.execute("ALTER TABLE components ADD COLUMN sku TEXT")
        rows = conn.execute("SELECT component_id FROM components WHERE sku IS NULL OR TRIM(sku) = ''").fetchall()
        for row in rows:
            conn.execute("UPDATE components SET sku = ? WHERE component_id = ?", (f"LEGACY-{row['component_id']}", row["component_id"]))
    if "min_stock_level" not in columns:
        conn.execute("ALTER TABLE components ADD COLUMN min_stock_level INTEGER NOT NULL DEFAULT 10 CHECK (min_stock_level >= 0)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_components_sku_unique ON components(sku)")
    conn.commit()
    conn.close()


def get_status(quantity, min_stock_level=None):
    threshold = app.config.get("LOW_STOCK_THRESHOLD", 10) if min_stock_level is None else min_stock_level
    if quantity == 0:
        return "Out of Stock"
    if quantity <= threshold:
        return "Low Stock"
    return "Available"


def validate_component(form, current_component_id=None):
    sku = form.get("sku", "").strip().upper()
    name = form.get("component_name", "").strip()
    category = form.get("category", "").strip()
    quantity_text = form.get("quantity", "").strip()
    price_text = form.get("price", "").strip()
    min_stock_text = form.get("min_stock_level", str(app.config.get("LOW_STOCK_THRESHOLD", 10))).strip()
    errors = []

    if not sku:
        errors.append("SKU is required.")
    elif len(sku) > 64:
        errors.append("SKU must be 64 characters or fewer.")
    if not name:
        errors.append("Component name is required.")
    if not category:
        errors.append("Category is required.")

    quantity = None
    try:
        if not quantity_text or str(int(quantity_text)) != quantity_text:
            raise ValueError
        quantity = int(quantity_text)
        if quantity < 0:
            errors.append("Quantity cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Quantity must be a whole number.")

    price = None
    try:
        price = float(price_text)
        if not math.isfinite(price) or price < 0:
            errors.append("Price must be a finite, non-negative number.")
    except (ValueError, TypeError):
        errors.append("Price must be a valid number.")

    min_stock_level = None
    try:
        if not min_stock_text or str(int(min_stock_text)) != min_stock_text:
            raise ValueError
        min_stock_level = int(min_stock_text)
        if min_stock_level < 0:
            errors.append("Minimum stock level cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Minimum stock level must be a non-negative whole number.")

    if sku:
        conn = get_db_connection()
        query = "SELECT component_id FROM components WHERE UPPER(sku) = UPPER(?)"
        params = [sku]
        if current_component_id is not None:
            query += " AND component_id != ?"
            params.append(current_component_id)
        duplicate = conn.execute(query, params).fetchone()
        conn.close()
        if duplicate:
            errors.append("SKU already exists. Please use a unique SKU.")

    if errors:
        return None, errors
    return {
        "sku": sku,
        "component_name": name,
        "category": category,
        "quantity": quantity,
        "price": price,
        "min_stock_level": min_stock_level,
    }, []


@app.route("/")
def dashboard():
    conn = get_db_connection()
    components = conn.execute("SELECT * FROM components").fetchall()
    conn.close()
    statuses = [get_status(c["quantity"], c["min_stock_level"]) for c in components]
    return render_template(
        "dashboard.html", total=len(components), available=statuses.count("Available"),
        low_stock=statuses.count("Low Stock"), out_of_stock=statuses.count("Out of Stock"),
    )


@app.route("/inventory")
def inventory():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    conn = get_db_connection()
    components = conn.execute("SELECT * FROM components ORDER BY component_id").fetchall()
    conn.close()
    filtered = []
    for component in components:
        if search and search.casefold() not in (component["component_name"] + " " + (component["sku"] or "")).casefold():
            continue
        if category and component["category"] != category:
            continue
        if status and get_status(component["quantity"], component["min_stock_level"]) != status:
            continue
        filtered.append(component)
    categories = sorted({c["category"] for c in components})
    return render_template("inventory.html", components=filtered, categories=categories,
        search=search, selected_category=category, selected_status=status,
        get_status=get_status)


@app.route("/add", methods=["GET", "POST"])
def add_component():
    if request.method == "POST":
        data, errors = validate_component(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_component.html"), 400
        conn = get_db_connection()
        try:
            conn.execute("""INSERT INTO components
                (sku, component_name, category, quantity, price, min_stock_level)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (data["sku"], data["component_name"], data["category"], data["quantity"], data["price"], data["min_stock_level"]))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("SKU already exists. Please use a unique SKU.", "error")
            return render_template("add_component.html"), 400
        finally:
            conn.close()
        flash("Component added successfully.", "success")
        return redirect(url_for("inventory"))
    return render_template("add_component.html")


@app.route("/edit/<int:component_id>", methods=["GET", "POST"])
def edit_component(component_id):
    conn = get_db_connection()
    component = conn.execute("SELECT * FROM components WHERE component_id = ?", (component_id,)).fetchone()
    conn.close()
    if component is None:
        flash("Component not found.", "error")
        return redirect(url_for("inventory"))
    if request.method == "POST":
        data, errors = validate_component(request.form, current_component_id=component_id)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("edit_component.html", component=component), 400
        conn = get_db_connection()
        try:
            conn.execute("""UPDATE components SET sku = ?, component_name = ?, category = ?,
                quantity = ?, price = ?, min_stock_level = ? WHERE component_id = ?""",
                (data["sku"], data["component_name"], data["category"], data["quantity"], data["price"], data["min_stock_level"], component_id))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("SKU already exists. Please use a unique SKU.", "error")
            return render_template("edit_component.html", component=component), 400
        finally:
            conn.close()
        flash("Component updated successfully.", "success")
        return redirect(url_for("inventory"))
    return render_template("edit_component.html", component=component)


@app.route("/delete/<int:component_id>", methods=["POST"])
def delete_component(component_id):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM components WHERE component_id = ?", (component_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    flash("Component deleted successfully." if deleted else "Component not found.", "success" if deleted else "error")
    return redirect(url_for("inventory"))


@app.route("/report")
def report():
    conn = get_db_connection()
    components = conn.execute("SELECT * FROM components ORDER BY component_id").fetchall()
    conn.close()
    available, low_stock, out_of_stock = [], [], []
    for component in components:
        status = get_status(component["quantity"], component["min_stock_level"])
        if status == "Available": available.append(component)
        elif status == "Low Stock": low_stock.append(component)
        else: out_of_stock.append(component)
    return render_template("report.html", available=available, low_stock=low_stock, out_of_stock=out_of_stock)


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
