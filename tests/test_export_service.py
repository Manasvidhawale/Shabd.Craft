"""
Shabd.Craft — Tests: Export Service & Production Code Generation
"""

import ast
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.export_service import export_results_csv, export_results_json, generate_production_code


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

    def test_generates_hardened_harness_python_syntax(self):
        snippets = generate_production_code(
            system_prompt="You are a classifier.",
            user_prompt="Classify: {{input}}",
            model="gpt-4o",
            include_harness=True,
            output_format="json",
            required_json_keys=["category", "sentiment"],
        )
        parsed = ast.parse(snippets["openai_python"])
        assert parsed is not None
        assert "execute_with_harness" in snippets["openai_python"]
        assert "sanitize_untrusted_input" in snippets["openai_python"]
        assert "category" in snippets["openai_python"]
        assert "gpt-4o" in snippets["openai_python"]


class TestEvaluationExports:
    def test_exports_snapshotted_inputs_and_run_context(self):
        csv_output = export_results_csv([{
            "evaluation_run_id": "run-1", "test_case_id": "case-1",
            "input_data_snapshot": "input at run time",
            "expected_output_snapshot": "reference at run time",
            "generated_output": "answer", "overall_score": 88,
        }])
        assert "run-1" in csv_output
        assert "input at run time" in csv_output
        assert "reference at run time" in csv_output

        json_output = export_results_json(
            {"id": "experiment-1"}, [], [], [],
            [{"id": "run-1", "signature": "stable"}],
        )
        assert '"evaluation_runs"' in json_output
        assert '"signature": "stable"' in json_output

