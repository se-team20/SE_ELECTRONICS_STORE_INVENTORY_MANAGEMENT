
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["DATABASE"] = str(
    Path(os.environ.get("DATABASE", BASE_DIR / "database.db")).resolve()
)
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "Set the SECRET_KEY environment variable before starting the app."
    )


def get_db_connection():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS components (
                component_id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL
            )
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
    username = username.strip()

    if not username or len(username) > 100:
        raise ValueError("Username must contain 1–100 characters.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
    finally:
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


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

    try:
        quantity = int(quantity_text)
        if quantity < 0:
            errors.append("Quantity cannot be negative.")
    except (ValueError, TypeError):
        quantity = None
        errors.append("Quantity must be a whole number.")

    try:
        price = float(price_text)
        if not 0 <= price < float("inf"):
            errors.append("Price must be a non-negative number.")
    except (ValueError, TypeError):
        price = None
        errors.append("Price must be a valid number.")

    if errors:
        return None, errors

    return {
        "component_name": name,
        "category": category,
        "quantity": quantity,
        "price": price,
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

    return render_template(
        "dashboard.html",
        total=len(components),
        available=sum(
            get_status(c["quantity"]) == "Available" for c in components
        ),
        low_stock=sum(
            get_status(c["quantity"]) == "Low Stock" for c in components
        ),
        out_of_stock=sum(
            get_status(c["quantity"]) == "Out of Stock" for c in components
        ),
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
        if search and search.casefold() not in component[
            "component_name"
        ].casefold():
            continue
        if category and component["category"] != category:
            continue
        if status and get_status(component["quantity"]) != status:
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

        if component is None:
            flash("Component not found.", "error")
            return redirect(url_for("inventory"))

        if request.method == "POST":
            data, errors = validate_component(request.form)
            if errors:
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
            flash("Component updated successfully.", "success")
            return redirect(url_for("inventory"))

    finally:
        conn.close()

    return render_template("edit_component.html", component=component)


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


@app.cli.command("create-user")
def create_user_command():
    """Create a user using environment-provided credentials."""
    username = os.environ.get("NEW_USERNAME")
    password = os.environ.get("NEW_PASSWORD")

    if not username or not password:
        raise SystemExit(
            "Set NEW_USERNAME and NEW_PASSWORD before running this command."
        )

    initialize_database()
    try:
        create_user(username, password)
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise SystemExit(f"Could not create user: {exc}") from exc

    print(f"User '{username}' created successfully.")


initialize_database()

if __name__ == "__main__":
    app.run(debug=False)
