            (component_id,),
        )
        conn.commit()
        deleted = cursor.rowcount
    finally:
        conn.close()

    if deleted:
        log_action("DELETE_COMPONENT", component_id)
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
