"""
Shabd.Craft — Tests: Template Engine & Prompt Engine
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.template_engine import (
    analyze_prompt_structure,
    extract_variables,
    preview_template,
    render_template,
    validate_template,
)
from src.schemas import (
    PromptVersion, FewShotExample, PromptingTechnique, OutputFormat,
)
from src.prompt_engine import construct_prompt, build_few_shot_section


class TestTemplateEngine:
    def test_extract_variables_basic(self):
        result = extract_variables("Hello {{name}}, welcome to {{place}}!")
        assert result == ["name", "place"]

    def test_extract_variables_empty(self):
        assert extract_variables("No variables here.") == []

    def test_extract_variables_duplicates(self):
        result = extract_variables("{{x}} and {{x}} again")
        assert result == ["x"]

    def test_render_template_basic(self):
        result = render_template("Hello {{name}}!", {"name": "World"})
        assert result == "Hello World!"

    def test_render_template_multiple(self):
        result = render_template("{{a}} and {{b}}", {"a": "X", "b": "Y"})
        assert result == "X and Y"

    def test_render_template_missing_variable(self):
        with pytest.raises(ValueError, match="Missing template variables"):
            render_template("Hello {{name}}!", {})

    def test_render_template_extra_variables(self):
        result = render_template("Hi {{name}}!", {"name": "Bob", "extra": "ignored"})
        assert result == "Hi Bob!"

    def test_validate_template_valid(self):
        result = validate_template("Analyze {{input_text}} carefully.")
        assert result["variables"] == ["input_text"]

    def test_validate_template_empty(self):
        result = validate_template("")
        assert "empty" in result["warnings"][0].lower()

    def test_preview_template_with_values(self):
        result = preview_template("Hello {{name}}!", {"name": "Alice"})
        assert result == "Hello Alice!"

    def test_preview_template_without_values(self):
        result = preview_template("Hello {{name}}!")
        assert result == "Hello [name]!"

    def test_analyze_prompt_structure_catches_duplicate_and_missing_vars(self):
        text = "You are an expert Data Analyst and your task is to summarize the given dataset."
        res = analyze_prompt_structure(
            system_prompt=text,
            user_prompt=text,
            technique="role_based",
        )
        assert res["score"] < 60
        assert res["grade"] in ("Weak", "Moderate")
        assert any("identical" in i.lower() for i in res["issues"])
        assert any("{{variable}}" in i.lower() for i in res["issues"])

    def test_analyze_prompt_structure_rewards_well_engineered_prompt(self):
        res = analyze_prompt_structure(
            system_prompt="You are a senior data analyst. Respond concisely in 3 bullet points.",
            user_prompt="Summarize key trends in the dataset below:\n<user_input>{{dataset}}</user_input>",
            technique="role_based",
            output_format="bullet_points",
        )
        assert res["score"] >= 90
        assert res["grade"] == "Strong"
        assert res["issues"] == []


class TestPromptEngine:
    def test_build_few_shot_section_empty(self):
        assert build_few_shot_section([]) == ""

    def test_build_few_shot_section_single(self):
        examples = [FewShotExample(input_text="Hi", output_text="Hello")]
        result = build_few_shot_section(examples)
        assert "Example 1:" in result
        assert "Hi" in result
        assert "Hello" in result

    def test_build_few_shot_section_multiple(self):
        examples = [
            FewShotExample(input_text="A", output_text="1"),
            FewShotExample(input_text="B", output_text="2"),
        ]
        result = build_few_shot_section(examples)
        assert "Example 1:" in result
        assert "Example 2:" in result

    def test_construct_prompt_zero_shot(self):
        version = PromptVersion(
            experiment_id="test",
            system_prompt="You are a helper.",
            user_prompt_template="Analyze: {{input_text}}",
            technique=PromptingTechnique.ZERO_SHOT,
        )
        system, user = construct_prompt(version, input_data="test data")
        assert system == "You are a helper."
        assert "test data" in user

    def test_construct_prompt_few_shot(self):
        version = PromptVersion(
            experiment_id="test",
            system_prompt="",
            user_prompt_template="Classify: {{input_text}}",
            technique=PromptingTechnique.FEW_SHOT,
            few_shot_examples=[
                FewShotExample(input_text="good", output_text="positive"),
                FewShotExample(input_text="bad", output_text="negative"),
            ],
        )
        _, user = construct_prompt(version, input_data="test")
        assert "Example 1:" in user
        assert "Example 2:" in user
        assert "positive" in user

    def test_construct_prompt_json_format(self):
        version = PromptVersion(
            experiment_id="test",
            user_prompt_template="Extract data",
            output_format=OutputFormat.JSON,
        )
        _, user = construct_prompt(version)
        assert "JSON" in user

    def test_construct_prompt_chain_of_thought(self):
        version = PromptVersion(
            experiment_id="test",
            user_prompt_template="Solve: {{input}}",
            technique=PromptingTechnique.CHAIN_OF_THOUGHT,
        )
        _, user = construct_prompt(version, input_data="2 + 2 * 3")
        assert "2 + 2 * 3" in user
        assert "step by step" in user.lower()

    def test_construct_prompt_chain_of_thought_no_duplicate(self):
        version = PromptVersion(
            experiment_id="test",
            user_prompt_template="Solve step by step: {{input}}",
            technique=PromptingTechnique.CHAIN_OF_THOUGHT,
        )
        _, user = construct_prompt(version, input_data="x=5")
        assert user.lower().count("step by step") == 1

    def test_construct_prompt_task_decomposition_adds_scaffold(self):
        version = PromptVersion(
            experiment_id="test",
            user_prompt_template="Analyze: {{input}}",
            technique=PromptingTechnique.TASK_DECOMPOSITION,
        )
        _, user = construct_prompt(version, input_data="sales data")
        assert "Step 1:" in user
        assert "Analyze: sales data" in user

    def test_construct_prompt_task_decomposition_preserves_existing_steps(self):
        version = PromptVersion(
            experiment_id="test",
            user_prompt_template="Step 1: Read.\nStep 2: Summarize {{input}}",
            technique=PromptingTechnique.TASK_DECOMPOSITION,
        )
        _, user = construct_prompt(version, input_data="report")
        assert not user.startswith("Complete this task sequentially")
        assert "Step 1: Read." in user
