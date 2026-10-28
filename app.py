    if component is None:
        flash("Component not found.", "error")
        return redirect(url_for("inventory"))

    if request.method == "POST":
        data, errors = validate_component(
            request.form, current_component_id=component_id
        )
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("edit_component.html", component=component), 400

        conn = get_db_connection()
        try:
            conn.execute(
                """
                UPDATE components
                SET sku = ?, component_name = ?, category = ?, quantity = ?,
                    price = ?, min_stock_level = ?
                WHERE component_id = ?
                """,
                (
                    data["sku"],
                    data["component_name"],
                    data["category"],
                    data["quantity"],
                    data["price"],
                    data["min_stock_level"],
                    component_id,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("SKU already exists. Please use a unique SKU.", "error")
            return render_template("edit_component.html", component=component), 400
        finally:
            conn.close()

        log_action("EDIT_COMPONENT", component_id)
        flash("Component updated successfully.", "success")
        return redirect(url_for("inventory"))

    return render_template("edit_component.html", component=component)


@app.route("/delete/<int:component_id>", methods=["POST"])
@login_required
def delete_component(component_id):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM components WHERE component_id = ?", (component_id,)
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

    available, low_stock, out_of_stock = [], [], []
    for component in components:
        status = get_status(component["quantity"], component["min_stock_level"])
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
