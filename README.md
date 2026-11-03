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

The SQLite database is initialized automatically when the application starts.

### 4. Open the application

Open the following URL in your browser:

```text
http://127.0.0.1:5000
```

Log in using an account configured for the application.

## Database Configuration

The application uses an SQLite database named `database.db` by default.

The database stores:
- Component details
- SKU information
- Component quantities and prices
- Minimum stock levels
- User account information

The application also supports environment variables for database configuration, the secret key, and the low-stock threshold.

## Automated Testing

Run the automated test suite from the project directory:

```bash
python -m pytest -v
```

The tests cover:
- Component creation, updating, and deletion
- Input validation
- Duplicate SKU prevention
- Stock-status boundaries
- Dashboard calculations
- Inventory reports
- CSV export
- Database integrity checks

## Continuous Integration

GitHub Actions is configured to install the required dependencies and execute automated tests when changes are pushed to supported branches or pull requests are created against the main branch.

## Project Scope

The system provides a centralized solution for electronic component inventory management. It supports inventory operations, stock monitoring, reporting, data validation, and automated testing.