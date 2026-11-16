"""
Shabd.Craft — Tests: Streamlit UI Smoke Tests
"""

import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).parent.parent))


_ROOT = Path(__file__).parent.parent


def test_prompt_workshop_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "1_Prompt_Workshop.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_app_entrypoint_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "app.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_settings_page_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "7_Settings.py"), default_timeout=15)
    at.run()
    assert not at.exception


def test_prompt_library_renders_without_errors():
    at = AppTest.from_file(str(_ROOT / "views" / "6_Prompt_Library.py"), default_timeout=15)
    at.run()
    assert not at.exception
