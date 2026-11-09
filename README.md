# Electronics Store Inventory Management System

A web-based application developed using Python Flask and SQLite to manage electronic component inventory efficiently. It helps users track component quantities, monitor stock availability, identify low-stock items, and generate inventory reports.

## Features

- User login and logout
- Add new electronic components
- Update component details
- Delete components
- Search and filter inventory
- Check component availability
- Automatic low-stock detection
- Dashboard with inventory statistics
- Inventory reports categorized by stock status
- Export inventory reports as CSV files
- Input validation and duplicate SKU prevention

## Technologies Used

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Testing:** Pytest
- **CI/CD:** GitHub Actions

## Project Setup and Execution

### 1. Clone the repository

```bash
git clone https://github.com/se-team20/SE_ELECTRONICS_STORE_INVENTORY_MANAGEMENT.git
cd SE_ELECTRONICS_STORE_INVENTORY_MANAGEMENT
```

### 2. Install dependencies

```bash
python -m pip install Flask pytest
```

### 3. Run the application

```bash
python app.py
```

### 4. Open the application

Open the following URL in your browser:

```text
http://127.0.0.1:5000
```

Log in using an account configured for the application.

## Database Configuration

The application uses an SQLite database named `database.db` by default.

The database stores component details, SKU information, quantities, prices, minimum stock levels, and user account information.

## Authentication and Security

- User login and logout functionality.
- Role-based access control, if configured in the application.
- Protected inventory operations, if configured in the application.
- Authentication and authorization tests, if included in the test suite.

## Automated Testing

Run the automated test suite from the project directory:

```bash
python -m pytest -v
```

The tests cover inventory operations, input validation, stock status, database constraints, and other implemented functionality.

## Continuous Integration

GitHub Actions is configured to run automated tests when changes are pushed to supported branches or pull requests are created against the main branch.

## Project Scope

The system provides a centralized solution for electronic component inventory management. It supports inventory operations, stock monitoring, reporting, data validation, and automated testing.