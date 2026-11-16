"""
Shabd.Craft — Tests: Test Synthesizer & Multi-Column Mapping
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.schemas import PromptVersion, PromptingTechnique
from src.test_synthesizer import generate_synthetic_test_cases, _generate_deterministic_cases
from src.export_service import parse_test_cases_csv
from src.prompt_engine import construct_prompt


class TestSynthesizer:
    def test_deterministic_cases_count_and_types(self):
        ver = PromptVersion(
            experiment_id="exp-1",
            system_prompt="You are an analyst.",
            user_prompt_template="Classify feedback: {{feedback}}",
        )
        cases = _generate_deterministic_cases(ver, count=3, category="classification")
        assert len(cases) == 3
        for c in cases:
            assert c.input_data != ""
            assert len(c.input_data) > 5
            assert c.expected_output != ""

    def test_synthesizer_fallback_generates_cases(self):
        ver = PromptVersion(
            experiment_id="exp-2",
            system_prompt="Summarizer.",
            user_prompt_template="Summarize: {{input}}",
        )
        cases = generate_synthetic_test_cases(ver, count=4, category="summarization")
        assert len(cases) == 4


class TestMultiColumnMapping:
    def test_multi_column_csv_packs_json(self):
        csv_content = """context,question,expected_output
Austin Texas,Where is HQ?,Austin
Berlin Germany,Where is datacenter?,Berlin"""
        parsed, errors = parse_test_cases_csv(csv_content)
        assert len(errors) == 0
        assert len(parsed) == 2
        assert '"context": "Austin Texas"' in parsed[0]["input_data"]
        assert '"question": "Where is HQ?"' in parsed[0]["input_data"]
        assert parsed[0]["expected_output"] == "Austin"

    def test_construct_prompt_unpacks_json_variables(self):
        ver = PromptVersion(
            experiment_id="exp-3",
            system_prompt="You answer questions based on context.",
            user_prompt_template="Context: {{context}}\n\nQuestion: {{question}}",
        )
        json_input = '{"context": "Google was founded in 1998.", "question": "When was Google founded?"}'
        _, user = construct_prompt(ver, input_data=json_input)
        assert "Google was founded in 1998." in user
        assert "When was Google founded?" in user
        assert "{{context}}" not in user
        assert "{{question}}" not in user
