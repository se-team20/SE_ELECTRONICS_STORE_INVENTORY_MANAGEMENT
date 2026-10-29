
import math
import os
import sqlite3
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, flash, redirect, render_template, request, session, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "dev-only-change-this-before-deployment"
)
app.config["DATABASE"] = os.environ.get("DATABASE", "database.db")
app.config["LOW_STOCK_THRESHOLD"] = int(
    os.environ.get("LOW_STOCK_THRESHOLD", "10")
)


def get_db_connection():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    """Create inventory and user tables and migrate older databases."""
    conn = get_db_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS components (
                component_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE,
                component_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                price REAL NOT NULL CHECK (price >= 0),
                min_stock_level INTEGER NOT NULL DEFAULT 10
                    CHECK (min_stock_level >= 0)
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(components)")
        }

        if "sku" not in columns:
            conn.execute("ALTER TABLE components ADD COLUMN sku TEXT")

        if "min_stock_level" not in columns:
            conn.execute("""
                ALTER TABLE components
                ADD COLUMN min_stock_level INTEGER NOT NULL DEFAULT 10
                CHECK (min_stock_level >= 0)
            """)

        # Assign SKUs to existing rows that do not have one.
        rows = conn.execute("""
            SELECT component_id FROM components
            WHERE sku IS NULL OR TRIM(sku) = ''
        """).fetchall()

        for row in rows:
            conn.execute(
                "UPDATE components SET sku = ? WHERE component_id = ?",
                (f"LEGACY-{row['component_id']}", row["component_id"]),
            )

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_components_sku_unique
            ON components(sku)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)

        conn.commit()
    finally:
        conn.close()


def create_user(username, password):
    """Create a user with a securely hashed password."""
    username = (username or "").strip()

    if not username:
        raise ValueError("Username is required.")

    if len(username) > 100:
        raise ValueError("Username must be 100 characters or fewer.")

    if not password or len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    initialize_database()
    password_hash = generate_password_hash(password)
    conn = get_db_connection()

    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
    finally:
        conn.close()


def login_required(view):
    """Restrict a view to authenticated users."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.url))

        return view(*args, **kwargs)

    return wrapped_view


def get_status(quantity, min_stock_level=None):
    threshold = (
        app.config.get("LOW_STOCK_THRESHOLD", 10)
        if min_stock_level is None
        else min_stock_level
    )

    if quantity == 0:
        return "Out of Stock"
    if quantity <= threshold:
        return "Low Stock"
    return "Available"


def validate_component(form, current_component_id=None):
    sku = form.get("sku", "").strip().upper()

    # Support older forms and tests that do not submit a SKU.
    if not sku:
        sku = "AUTO-" + os.urandom(8).hex().upper()

    name = form.get("component_name", "").strip()
    category = form.get("category", "").strip()
    quantity_text = form.get("quantity", "").strip()
    price_text = form.get("price", "").strip()
    min_stock_text = form.get(
        "min_stock_level",
        str(app.config.get("LOW_STOCK_THRESHOLD", 10)),
    ).strip()

    errors = []

    if len(sku) > 64:
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
        if (
            not min_stock_text
            or str(int(min_stock_text)) != min_stock_text
        ):
            raise ValueError

        min_stock_level = int(min_stock_text)

        if min_stock_level < 0:
            errors.append("Minimum stock level cannot be negative.")
    except (ValueError, TypeError):
        errors.append(
            "Minimum stock level must be a non-negative whole number."
        )

    if sku:
        conn = get_db_connection()
        try:
            query = """
                SELECT component_id FROM components
                WHERE UPPER(sku) = UPPER(?)
            """
            params = [sku]

            if current_component_id is not None:
                query += " AND component_id != ?"
                params.append(current_component_id)

            duplicate = conn.execute(query, params).fetchone()
        finally:
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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]

            next_url = request.args.get("next", "")
            parsed_url = urlparse(next_url)

            # Prevent redirects to external websites.
            if (
                next_url
                and not parsed_url.scheme
                and not parsed_url.netloc
                and next_url.startswith("/")
                and not next_url.startswith("//")
            ):
                return redirect(next_url)

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    conn = get_db_connection()
    try:
        components = conn.execute(
            "SELECT * FROM components"
        ).fetchall()
    finally:
        conn.close()

    statuses = [
        get_status(c["quantity"], c["min_stock_level"])
        for c in components
    ]

    return render_template(
        "dashboard.html",
        total=len(components),
        available=statuses.count("Available"),
        low_stock=statuses.count("Low Stock"),
        out_of_stock=statuses.count("Out of Stock"),
    )


@app.route("/inventory")
@login_required
def inventory():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db_connection()
    try:
        components = conn.execute(
            "SELECT * FROM components ORDER BY component_id"
        ).fetchall()
    finally:
        conn.close()

    filtered = []

    for component in components:
        searchable_text = (
            (component["component_name"] or "")
            + " "
            + (component["sku"] or "")
        )

        if search and search.casefold() not in searchable_text.casefold():
            continue

        if category and component["category"] != category:
            continue

        if (
            status
            and get_status(
                component["quantity"], component["min_stock_level"]
            ) != status
        ):
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
@login_required
def add_component():
    if request.method == "POST":
        data, errors = validate_component(request.form)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_component.html"), 400

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO components
                (sku, component_name, category, quantity, price,
                 min_stock_level)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data["sku"],
                data["component_name"],
                data["category"],
                data["quantity"],
                data["price"],
                data["min_stock_level"],
            ))
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
@login_required
def edit_component(component_id):
    conn = get_db_connection()
    try:
        component = conn.execute(
            "SELECT * FROM components WHERE component_id = ?",
            (component_id,),
        ).fetchone()
    finally:
        conn.close()

    if component is None:
        flash("Component not found.", "error")
        return redirect(url_for("inventory"))

    if request.method == "POST":
        data, errors = validate_component(
            request.form,
            current_component_id=component_id,
        )

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "edit_component.html", component=component
            ), 400

        conn = get_db_connection()
        try:
            conn.execute("""
                UPDATE components
                SET sku = ?, component_name = ?, category = ?,
                    quantity = ?, price = ?, min_stock_level = ?
                WHERE component_id = ?
            """, (
                data["sku"],
                data["component_name"],
                data["category"],
                data["quantity"],
                data["price"],
                data["min_stock_level"],
                component_id,
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("SKU already exists. Please use a unique SKU.", "error")
            return render_template(
                "edit_component.html", component=component
            ), 400
        finally:
            conn.close()

        flash("Component updated successfully.", "success")
        return redirect(url_for("inventory"))

    return render_template(
        "edit_component.html", component=component
    )


@app.route("/delete/<int:component_id>", methods=["POST"])
@login_required
def delete_component(component_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM components WHERE component_id = ?",
            (component_id,),
        )
        conn.commit()
        deleted = cursor.rowcount
    finally:
        conn.close()

    if deleted:
        flash("Component deleted successfully.", "success")
    else:
        flash("Component not found.", "error")

    return redirect(url_for("inventory"))


@app.route("/report")
@login_required
def report():
    conn = get_db_connection()
    try:
        components = conn.execute(
            "SELECT * FROM components ORDER BY component_id"
        ).fetchall()
    finally:
        conn.close()

    available = []
    low_stock = []
    out_of_stock = []

    for component in components:
        status = get_status(
            component["quantity"], component["min_stock_level"]
        )

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


@app.cli.command("create-user")
def create_user_command():
    """Create a user using NEW_USERNAME and NEW_PASSWORD environment variables."""
    username = os.environ.get("NEW_USERNAME", "")
    password = os.environ.get("NEW_PASSWORD", "")

    try:
        create_user(username, password)
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise SystemExit(f"Could not create user: {exc}") from exc

    print(f"User '{username.strip()}' created successfully.")


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
