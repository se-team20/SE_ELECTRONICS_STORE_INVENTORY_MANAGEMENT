import csv
import io
import math
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["DATABASE"] = str(
    Path(os.environ.get("DATABASE", BASE_DIR / "database.db")).resolve()
)
app.config["LOW_STOCK_THRESHOLD"] = int(
    os.environ.get("LOW_STOCK_THRESHOLD", "10")
)

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "Set the SECRET_KEY environment variable before starting the app."
    )

app.config["SECRET_KEY"] = _secret_key
app.secret_key = _secret_key

VALID_ROLES = {
    "Administrator",
    "Store Manager",
    "Inventory Staff",
}


def get_db_connection():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    """Create tables and migrate older databases safely."""
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
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Inventory Staff'
            )
        """)

        user_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)")
        }
        if "role" not in user_columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN role TEXT NOT NULL DEFAULT 'Inventory Staff'
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                component_id INTEGER,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    finally:
        conn.close()


def create_user(username, password, role="Inventory Staff"):
    """Create a user with a hashed password and validated role."""
    username = (username or "").strip()

    if not username or len(username) > 100:
        raise ValueError("Username must contain 1–100 characters.")
    if not password or len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    if role not in VALID_ROLES:
        raise ValueError("Invalid role.")

    initialize_database()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, generate_password_hash(password), role),
        )
        conn.commit()
    finally:
        conn.close()


def login_required(view):
    """Require the user to be logged in."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    """Require authentication and one of the specified roles."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                return "Forbidden: insufficient permissions", 403
            return view(*args, **kwargs)

        return wrapped_view

    return decorator



def log_action(action, component_id=None, conn=None):
    """Record an authenticated user's inventory action."""
    user_id = session.get("user_id")
    username = session.get("username")

    if user_id is None or not username:
        raise RuntimeError("An authenticated user is required.")

    if conn is None:
        raise ValueError("A database connection is required.")

    conn.execute(
        """
        INSERT INTO audit_logs
            (user_id, username, action, component_id)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, username, action, component_id),
    )



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

    try:
        if not quantity_text or str(int(quantity_text)) != quantity_text:
            raise ValueError
        quantity = int(quantity_text)
        if quantity < 0:
            errors.append("Quantity cannot be negative.")
    except (ValueError, TypeError):
        quantity = None
        errors.append("Quantity must be a non-negative whole number.")

    try:
        price = float(price_text)
        if not math.isfinite(price) or price < 0:
            raise ValueError
    except (ValueError, TypeError):
        price = None
        errors.append("Price must be a finite, non-negative number.")

    try:
        if not min_stock_text or str(int(min_stock_text)) != min_stock_text:
            raise ValueError
        min_stock_level = int(min_stock_text)
        if min_stock_level < 0:
            raise ValueError
    except (ValueError, TypeError):
        min_stock_level = None
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
            errors.append("SKU already exists. Use a unique SKU.")

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
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    error = None

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
            session["role"] = user["role"]
            session.permanent = True

            destination = request.args.get("next", "")
            if destination.startswith("/") and not destination.startswith("//"):
                return redirect(destination)

            return redirect(url_for("dashboard"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
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
            f"{component['component_name']} {component['sku'] or ''}"
        ).casefold()

        if search and search.casefold() not in searchable_text:
            continue
        if category and component["category"] != category:
            continue
        if status and get_status(
            component["quantity"], component["min_stock_level"]
        ) != status:
            continue

        filtered.append(component)

    return render_template(
        "inventory.html",
        components=filtered,
        categories=sorted({c["category"] for c in components}),
        search=search,
        selected_category=category,
        selected_status=status,
        get_status=get_status,
    )


@app.route("/add", methods=["GET", "POST"])
@role_required("Administrator", "Store Manager")
def add_component():
    if request.method == "POST":
        data, errors = validate_component(request.form)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_component.html"), 400

        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO components
                    (sku, component_name, category, quantity, price,
                     min_stock_level)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    data["sku"],
                    data["component_name"],
                    data["category"],
                    data["quantity"],
                    data["price"],
                    data["min_stock_level"],
                ),
            )
            component_id = cursor.lastrowid

            log_action("ADD_COMPONENT", component_id, conn)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("SKU already exists. Use a unique SKU.", "error")
            return render_template("add_component.html"), 400
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        
        flash("Component added successfully.", "success")
        return redirect(url_for("inventory"))

    return render_template("add_component.html")


@app.route("/edit/<int:component_id>", methods=["GET", "POST"])
@role_required("Administrator", "Store Manager")
def edit_component(component_id):
    conn = get_db_connection()
    try:
        component = conn.execute(
            "SELECT * FROM components WHERE component_id = ?",
            (component_id,),
        ).fetchone()
    except Exception:
        conn.rollback()
        raise
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
                "edit_component.html",
                component=component,
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
            log_action("EDIT_COMPONENT", component_id, conn)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("SKU already exists. Use a unique SKU.", "error")
            return render_template(
                "edit_component.html",
                component=component,
            ), 400
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        
        flash("Component updated successfully.", "success")
        return redirect(url_for("inventory"))

    return render_template(
        "edit_component.html", component=component
    )


@app.route("/delete/<int:component_id>", methods=["POST"])
@role_required("Administrator", "Store Manager")
def delete_component(component_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM components WHERE component_id = ?",
            (component_id,),
        )

        deleted = cursor.rowcount

        if deleted:
            log_action("DELETE_COMPONENT", component_id, conn)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

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
            component["quantity"],
            component["min_stock_level"],
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
@app.route("/export/csv")
@login_required
def export_csv():
    conn = get_db_connection()
    try:
        components = conn.execute(
            "SELECT * FROM components ORDER BY component_id"
        ).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Component ID",
        "Component Name",
        "Quantity",
        "Minimum Stock Level",
        "Status",
    ])

    for component in components:
        status = get_status(
            component["quantity"],
            component["min_stock_level"]
        )
        writer.writerow([
            component["component_id"],
            component["component_name"],
            component["quantity"],
            component["min_stock_level"],
            status,
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=inventory_report.csv"
        },
    )


@app.cli.command("create-user")
def create_user_command():
    """Create a user using environment-provided credentials."""
    username = os.environ.get("NEW_USERNAME")
    password = os.environ.get("NEW_PASSWORD")
    role = os.environ.get("NEW_ROLE", "Inventory Staff")

    if not username or not password:
        raise SystemExit(
            "Set NEW_USERNAME and NEW_PASSWORD before running this command."
        )

    initialize_database()

    try:
        create_user(username, password, role)
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise SystemExit(f"Could not create user: {exc}") from exc

    print(f"User '{username.strip()}' created successfully.")


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
