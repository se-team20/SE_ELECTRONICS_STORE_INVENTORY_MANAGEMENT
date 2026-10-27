
import ast
from pathlib import Path


def test_app_file_exists():
    assert Path("app.py").is_file()


def test_app_has_valid_python_syntax():
    source = Path("app.py").read_text(encoding="utf-8")
    ast.parse(source)


def test_database_file_exists():
    assert Path("database.db").is_file()
