"""
Shabd.Craft — Tests: Export Service & Production Code Generation
"""

import ast
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.export_service import generate_production_code


class TestGenerateProductionCode:
    def test_generates_valid_python_syntax(self):
        snippets = generate_production_code(
            system_prompt='You are an "expert" analyst.\nLine two.',
            user_prompt="Analyze: 'some text'\nReturn JSON.",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=512,
        )
        # Both Python snippets must parse cleanly via ast.parse
        ast.parse(snippets["openai_python"])
        ast.parse(snippets["langchain_python"])
        assert "gpt-4o-mini" in snippets["openai_python"]
        assert "ChatOpenAI" in snippets["langchain_python"]
        assert "https://api.openai.com/v1/chat/completions" in snippets["curl"]

    def test_replaces_demo_simulator_model(self):
        snippets = generate_production_code(
            system_prompt="Assistant",
            user_prompt="Hello",
            model="demo-simulator",
        )
        assert "demo-simulator" not in snippets["openai_python"]
        assert "gpt-3.5-turbo" in snippets["openai_python"]

