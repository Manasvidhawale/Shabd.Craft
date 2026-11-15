"""
Shabd.Craft — Tests: Pydantic Schemas
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError

from src.schemas import (
    PromptVersion, PromptTemplate, FewShotExample,
    TestCase, EvaluationResult, EvaluationWeights,
    CriterionScore, Experiment, OptimizationCandidate,
    VersionComparison, LLMRequest, LLMResponse,
    TaskCategory, PromptingTechnique, OutputFormat,
    ExecutionStatus, EvaluationMethod,
    _new_id, _now,
)


class TestHelpers:
    def test_new_id_format(self):
        id1 = _new_id()
        id2 = _new_id()
        assert len(id1) == 12
        assert id1 != id2
        assert id1.isalnum()

    def test_now_returns_iso_string(self):
        ts = _now()
        assert "T" in ts
        # Should be parseable as ISO 8601
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None


class TestTaskCategoryEnum:
    def test_valid_values(self):
        assert TaskCategory.SUMMARIZATION.value == "summarization"
        assert TaskCategory.EXTRACTION.value == "extraction"
        assert TaskCategory.SENTIMENT.value == "sentiment"
        assert TaskCategory.GENERAL.value == "general"

    def test_from_string(self):
        cat = TaskCategory("summarization")
        assert cat == TaskCategory.SUMMARIZATION


class TestPromptingTechniqueEnum:
    def test_all_techniques_exist(self):
        expected = ["zero_shot", "one_shot", "few_shot", "role_based",
                    "structured_output", "task_decomposition", "chain_of_thought"]
        for val in expected:
            assert PromptingTechnique(val)

    def test_invalid_technique(self):
        with pytest.raises(ValueError):
            PromptingTechnique("invalid_technique")


class TestFewShotExample:
    def test_valid_creation(self):
        ex = FewShotExample(input_text="Hello", output_text="Hi")
        assert ex.input_text == "Hello"
        assert ex.output_text == "Hi"

    def test_missing_fields_raises(self):
        with pytest.raises(ValidationError):
            FewShotExample(input_text="Hello")


class TestPromptVersion:
    def test_minimal_creation(self):
        pv = PromptVersion(
            experiment_id="exp-1",
            user_prompt_template="Summarize: {{text}}",
        )
        assert pv.experiment_id == "exp-1"
        assert pv.version_number == 1
        assert pv.version_label == "Original"
        assert pv.technique == PromptingTechnique.ZERO_SHOT
        assert pv.output_format == OutputFormat.TEXT
        assert pv.temperature == 0.7
        assert pv.max_tokens == 1024

    def test_id_auto_generated(self):
        pv1 = PromptVersion(experiment_id="e1", user_prompt_template="p1")
        pv2 = PromptVersion(experiment_id="e1", user_prompt_template="p2")
        assert pv1.id != pv2.id

    def test_few_shot_examples(self):
        examples = [
            FewShotExample(input_text="in1", output_text="out1"),
            FewShotExample(input_text="in2", output_text="out2"),
        ]
        pv = PromptVersion(
            experiment_id="exp-1",
            user_prompt_template="Classify: {{text}}",
            technique=PromptingTechnique.FEW_SHOT,
            few_shot_examples=examples,
        )
        assert len(pv.few_shot_examples) == 2

    def test_model_name_field_no_warning(self):
        # This should not raise any Pydantic protected namespace warning
        pv = PromptVersion(
            experiment_id="exp-1",
            user_prompt_template="test",
            model_name="gpt-4o",
        )
        assert pv.model_name == "gpt-4o"


class TestTestCase:
    def test_valid_creation(self):
        tc = TestCase(input_data="some input")
        assert tc.input_data == "some input"
        assert tc.expected_output == ""

    def test_strips_whitespace(self):
        tc = TestCase(input_data="  hello  ")
        assert tc.input_data == "hello"

    def test_empty_input_raises(self):
        with pytest.raises(ValidationError):
            TestCase(input_data="   ")

    def test_with_expected_output(self):
        tc = TestCase(input_data="hello", expected_output="expected result")
        assert tc.expected_output == "expected result"


class TestCriterionScore:
    def test_valid_score(self):
        cs = CriterionScore(name="accuracy", score=85.0)
        assert cs.score == 85.0

    def test_zero_score(self):
        cs = CriterionScore(name="relevance", score=0)
        assert cs.score == 0

    def test_max_score(self):
        cs = CriterionScore(name="clarity", score=100)
        assert cs.score == 100

    def test_score_above_max_raises(self):
        with pytest.raises(ValidationError):
            CriterionScore(name="clarity", score=101)

    def test_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            CriterionScore(name="clarity", score=-1)

    def test_with_explanation(self):
        cs = CriterionScore(name="format_compliance", score=90, explanation="Good JSON format")
        assert cs.explanation == "Good JSON format"


class TestEvaluationWeights:
    def test_defaults(self):
        w = EvaluationWeights()
        assert w.accuracy == 0.25
        assert w.relevance == 0.20
        assert w.instruction_adherence == 0.25
        assert w.clarity == 0.15
        assert w.format_compliance == 0.15

    def test_normalized_sums_to_one(self):
        w = EvaluationWeights(accuracy=2, relevance=2, instruction_adherence=2, clarity=2, format_compliance=2)
        n = w.normalized()
        assert abs(sum(n.values()) - 1.0) < 1e-9

    def test_all_zero_raises(self):
        w = EvaluationWeights(accuracy=0, relevance=0, instruction_adherence=0, clarity=0, format_compliance=0)
        with pytest.raises(ValueError, match="greater than zero"):
            w.normalized()

    def test_negative_weight_raises(self):
        with pytest.raises(ValidationError):
            EvaluationWeights(accuracy=-0.1)


class TestEvaluationResult:
    def test_defaults(self):
        er = EvaluationResult(
            test_case_id="tc1",
            prompt_version_id="pv1",
            experiment_id="exp1",
        )
        assert er.overall_score == 0.0
        assert er.execution_status == ExecutionStatus.PENDING
        assert er.is_demo is False
        assert er.error_message == ""

    def test_score_clamped(self):
        # Score must be 0–100
        with pytest.raises(ValidationError):
            EvaluationResult(
                test_case_id="tc1", prompt_version_id="pv1",
                experiment_id="exp1", overall_score=101,
            )

    def test_with_criterion_scores(self):
        er = EvaluationResult(
            test_case_id="tc1",
            prompt_version_id="pv1",
            experiment_id="exp1",
            overall_score=85.0,
            execution_status=ExecutionStatus.SUCCESS,
            criterion_scores=[
                CriterionScore(name="accuracy", score=90),
                CriterionScore(name="relevance", score=80),
            ],
        )
        assert len(er.criterion_scores) == 2


class TestExperiment:
    def test_valid_creation(self):
        exp = Experiment(name="Test Experiment")
        assert exp.name == "Test Experiment"
        assert exp.category == TaskCategory.GENERAL
        assert exp.status == ExecutionStatus.PENDING

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            Experiment(name="   ")

    def test_name_stripped(self):
        exp = Experiment(name="  My Experiment  ")
        assert exp.name == "My Experiment"


class TestOptimizationCandidate:
    def test_creation(self):
        oc = OptimizationCandidate(
            experiment_id="exp-1",
            original_version_id="ver-1",
            user_prompt_template="Better prompt: {{text}}",
            strategy="Explicit Instructions",
        )
        assert oc.experiment_id == "exp-1"
        assert oc.status == ExecutionStatus.PENDING
        assert oc.is_accepted is False
        assert oc.overall_score == 0.0


class TestLLMSchemas:
    def test_llm_request_defaults(self):
        req = LLMRequest(user_prompt="Hello")
        assert req.model == "gpt-3.5-turbo"
        assert req.temperature == 0.7
        assert req.max_tokens == 1024

    def test_llm_response_defaults(self):
        resp = LLMResponse(content="Response text")
        assert resp.content == "Response text"
        assert resp.is_demo is False
        assert resp.error == ""
        assert resp.total_tokens == 0


class TestVersionComparison:
    def test_creation(self):
        vc = VersionComparison(
            version_a_id="va",
            version_b_id="vb",
            version_a_overall=80.0,
            version_b_overall=90.0,
            winner="vb",
        )
        assert vc.winner == "vb"
        assert vc.version_a_overall == 80.0
