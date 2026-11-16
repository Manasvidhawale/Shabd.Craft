"""
Shabd.Craft — Tests: Streamlit UI Smoke Tests

Comprehensive smoke testing across all views using official Streamlit AppTest.
"""

import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).parent.parent))

_ROOT = Path(__file__).parent.parent


def test_app_entrypoint_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_home_page_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "0_Home.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_prompt_workshop_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "1_Prompt_Workshop.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_evaluation_lab_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "2_Evaluation_Lab.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_prompt_optimizer_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "3_Prompt_Optimizer.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_compare_versions_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "4_Compare_Versions.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_experiment_history_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "5_Experiment_History.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_prompt_library_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "6_Prompt_Library.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_settings_page_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "7_Settings.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_all_python_files_are_valid_in_python_311():
    """Verify every Python file parses cleanly under Python 3.11 without syntax errors."""
    import ast
    for py_file in _ROOT.glob("**/*.py"):
        if "venv" in py_file.parts or ".git" in py_file.parts:
            continue
        source = py_file.read_text(encoding="utf-8")
        # ast.parse guarantees Python 3.11 syntax compliance (e.g. no backslashes in f-strings)
        ast.parse(source, filename=str(py_file))

