# Electronics Store Inventory Management System (SEIMS)

## 1. Project Overview

The Electronics Store Inventory Management System (SEIMS) is a web-based application developed using Python Flask and SQLite. It provides an organized solution for managing electronic component inventory, monitoring stock availability, identifying low-stock items, and generating inventory reports.

The application helps inventory personnel maintain component records, manage stock quantities, and access inventory information through a centralized interface.

## 2. Features

- User login and logout
- Role-based user access
- Add new electronic components
- Update component details
- Delete component records
- Search and filter inventory
- Monitor component availability
- Automatic low-stock detection
- Dashboard displaying inventory statistics
- Inventory reports categorized by stock status
- Export inventory reports as CSV files
- Input validation
- Duplicate SKU prevention
- Authentication and inventory-related automated tests

## 3. Technologies Used

| Component | Technology |
|---|---|
| Backend | Python |
| Web Framework | Flask |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript, Jinja2 |
| Testing Framework | Pytest |
| Version Control | Git and GitHub |
| CI/CD | GitHub Actions |

## 4. Project Setup and Execution

### 4.1 Clone the Repository

```bash
git clone https://github.com/se-team20/SE_ELECTRONICS_STORE_INVENTORY_MANAGEMENT.git
cd SE_ELECTRONICS_STORE_INVENTORY_MANAGEMENT
```

### 4.2 Install Dependencies

Ensure Python is installed.

Install the required packages:

```bash
python -m pip install --upgrade pip
python -m pip install Flask pytest
```

### 4.3 Configure the Secret Key

The application requires a SECRET_KEY environment variable for session security.

For Windows PowerShell, generate a temporary development key:

```powershell
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
```

This key is temporary and must be configured again when opening a new PowerShell session.

For production deployment, use a securely managed secret rather than a hard-coded key.

### 4.4 Run the Application

Start the Flask application:

```bash
python app.py
```

### 4.5 Open the Application

Open a browser and visit:

```text
http://127.0.0.1:5000
```

Log in using an account configured for the application.

## 5. Database Configuration

The application uses SQLite as its database.

- Default database: `database.db`
- Database configuration can be overridden using the `DATABASE` environment variable.
- Foreign key enforcement is enabled for database connections.
- The default low-stock threshold is 10 units.

The low-stock threshold can be customized using the `LOW_STOCK_THRESHOLD` environment variable.

## 6. Authentication and Security

The application includes login and logout functionality and uses Flask session management.

The application uses Werkzeug password-hashing utilities for password verification and password hashing.

The SECRET_KEY environment variable is required to initialize the application securely.

Role definitions include:

- Administrator
- Store Manager
- Inventory Staff

Access to application operations is controlled through the implemented authentication and authorization mechanisms.

## 7. Automated Testing

The project uses Pytest for automated testing.

Run the test suite from the project directory:

```powershell
$env:SECRET_KEY = "seims-local-testing-key-2026"
python -m pytest -v
```

The test suite covers application functionality, authentication, inventory operations, validation, and other implemented features.

The test results should be verified against the latest execution before being reported.

## 8. Continuous Integration

GitHub Actions is configured to automate testing.

Workflow file:

```text
.github/workflows/tests.yml
```

The workflow:

1. Checks out the repository.
2. Sets up Python 3.12.
3. Installs Flask and Pytest.
4. Configures a test-only SECRET_KEY.
5. Executes the automated test suite.

The workflow is triggered by supported branch pushes and pull requests targeting the main branch.

## 9. Project Documentation

The project's documentation and reports are maintained in the `docs` directory.

### Software Requirements and Architecture

- [Software Requirements Specification (IEEE PDF)](docs/SEIMS_SRS_IEEE.pdf)
- [Software Architecture Document (IEEE PDF)](docs/SEIMS_SAD_IEEE.pdf)
- [Software Requirements Specification (DOCX)](docs/SRS_Electronics_Store_PES2UG24CS333.docx)
- [Software Architecture Document (DOCX)](docs/SAD_Electronics_Store_PES2UG24CS333.docx)

### Testing and Quality Reports

- [Test Plan](docs/Test_Plan_Electronics_Store_PES2UG24CS333.docx)
- [System Validation Report](docs/System_Validation_Report_PES2UG24CS333.docx)
- [Unit Test Report](docs/test-reports/Unit_Test_Report_PES2UG24CS333.docx)
- [Code Coverage Report](docs/Code_Coverage_Report_PES2UG24CS333.docx)
- [Branch Coverage Report](docs/Branch_Coverage_Report_PES2UG24CS333.docx)

## 10. Project Scope

SEIMS provides a centralized inventory management solution for electronic components. It supports inventory record management, stock monitoring, reporting, data validation, user authentication, and automated software testing.

The project is developed as part of the Software Engineering coursework, with emphasis on software development practices, testing, documentation, version control, and continuous integration.