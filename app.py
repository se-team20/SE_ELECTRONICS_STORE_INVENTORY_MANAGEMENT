
import os
import sqlite3
import secrets
import argparse
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    session, url_for, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"

app = Flask(__name__)

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "SECRET_KEY is missing. Set it before starting the application."
    )

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=1800,
)


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
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
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def get_status(quantity):
    if quantity == 0:
        return "Out of Stock"
    elif quantity <= 10:
        return "Low Stock"
    return "Available"


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

    total = len(components)
    available = sum(
        1 for c in components if get_status(c["quantity"]) == "Available"
    )
    low_stock = sum(
        1 for c in components if get_status(c["quantity"]) == "Low Stock"
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
        out_of_stock=out_of_stock,
    )


@app.route("/inventory")
@login_required
def inventory():
    conn = get_db_connection()
    try:
        components = conn.execute(
            "SELECT * FROM components"
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "inventory.html",
        components=components,
        get_status=get_status,
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_component():
    if request.method == "POST":
        component_name = request.form.get("component_name", "").strip()
        category = request.form.get("category", "").strip()

        try:
            quantity = int(request.form.get("quantity", ""))
            price = float(request.form.get("price", ""))
        except (ValueError, TypeError):
            abort(400, description="Invalid quantity or price.")

        if not component_name or not category:
            abort(400, description="Component name and category are required.")

        if quantity < 0 or price < 0:
            abort(400, description="Quantity and price cannot be negative.")

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO components
                    (component_name, category, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (component_name, category, quantity, price))
            conn.commit()
        finally:
            conn.close()

        return redirect(url_for("inventory"))

    return render_template("add_component.html")


@app.route("/delete/<int:component_id>", methods=["POST"])
@login_required
def delete_component(component_id):
    conn = get_db_connection()
    try:
        conn.execute(
            "DELETE FROM components WHERE component_id = ?",
            (component_id,),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/report")
@login_required
def report():
    conn = get_db_connection()
    try:
        components = conn.execute(
            "SELECT * FROM components"
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
