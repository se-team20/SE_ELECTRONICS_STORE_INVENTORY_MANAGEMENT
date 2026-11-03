# Electronics Store Inventory Management System

A web-based system for managing electronic component inventory.

## Features

- Add components
- Update components
- Delete components
- Search components
- Check component availability
- Low-stock detection
- Inventory reports
- Dashboard

## Technology

- Python (Flask)
- SQLite Database
- HTML
- CSS
- JavaScript

## Setup and Execution

1. Clone the repository:

   ```bash
   git clone https://github.com/se-team20/SE_ELECTRONICS_STORE_INVENTORY_MANAGEMENT.git
   cd SE_ELECTRONICS_STORE_INVENTORY_MANAGEMENT
   ```

2. Install Flask:

   ```bash
   py -m pip install flask
   ```

3. Run the application:

   ```bash
   py app.py
   ```

4. Open the application in your browser:

   `http://127.0.0.1:5000`

The tests cover inventory operations, input validation, stock status, and database constraints.

## Project Scope

The system supports electronic component inventory management, including adding, updating, deleting, searching, availability checking, low-stock detection, and inventory reporting.
## Authentication and Security

- Secure user login and logout using password hashing.
- Role-based access control for Administrators, Store Managers, and Inventory Staff.
- Protected inventory modification routes.
- Audit logging for inventory operations.
- Automated authentication and authorization tests.

## Testing

Authentication, authorization, inventory backend, frontend, and audit logging tests are included in the project.
