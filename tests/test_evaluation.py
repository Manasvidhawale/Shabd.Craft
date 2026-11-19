"""
Shabd.Craft — Tests: Evaluation Engine
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.schemas import (
    CriterionScore, EvaluationWeights, EvaluationResult,
    ExecutionStatus, OutputFormat,
)
from src.evaluation_engine import calculate_weighted_score, aggregate_results
from src.rule_based_evaluator import evaluate_rule_based


class TestEvaluationWeights:
    def test_normalized_equal(self):
        w = EvaluationWeights(accuracy=1, relevance=1, instruction_adherence=1, clarity=1, format_compliance=1)
        n = w.normalized()
        assert abs(sum(n.values()) - 1.0) < 0.001
        assert abs(n["accuracy"] - 0.2) < 0.001

    def test_normalized_custom(self):
        w = EvaluationWeights(accuracy=0.5, relevance=0.3, instruction_adherence=0.1, clarity=0.05, format_compliance=0.05)
        n = w.normalized()
        assert abs(sum(n.values()) - 1.0) < 0.001

    def test_all_zero_raises(self):
        w = EvaluationWeights(accuracy=0, relevance=0, instruction_adherence=0, clarity=0, format_compliance=0)
        with pytest.raises(ValueError, match="greater than zero"):
            w.normalized()

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError):
            EvaluationWeights(accuracy=-1)


class TestWeightedScore:
    def test_equal_weights(self):
        scores = [
            CriterionScore(name="accuracy", score=80),
            CriterionScore(name="relevance", score=90),
            CriterionScore(name="instruction_adherence", score=85),
            CriterionScore(name="clarity", score=75),
            CriterionScore(name="format_compliance", score=100),
        ]
        w = EvaluationWeights(accuracy=1, relevance=1, instruction_adherence=1, clarity=1, format_compliance=1)
        result = calculate_weighted_score(scores, w)
        assert result == 86.0

    def test_custom_weights(self):
        scores = [
            CriterionScore(name="accuracy", score=100),
            CriterionScore(name="relevance", score=0),
            CriterionScore(name="instruction_adherence", score=0),
            CriterionScore(name="clarity", score=0),
            CriterionScore(name="format_compliance", score=0),
        ]
        w = EvaluationWeights(accuracy=1, relevance=0, instruction_adherence=0, clarity=0, format_compliance=0)
        result = calculate_weighted_score(scores, w)
        assert result == 100.0

    def test_zero_scores(self):
        scores = [
            CriterionScore(name="accuracy", score=0),
            CriterionScore(name="relevance", score=0),
        ]
        w = EvaluationWeights()
        result = calculate_weighted_score(scores, w)
        assert result == 0.0


class TestRuleBasedEvaluator:
    def test_empty_output(self):
        scores = evaluate_rule_based("")
        assert all(s.score == 0 for s in scores)

    def test_valid_json(self):
        scores = evaluate_rule_based('{"key": "value"}', output_format=OutputFormat.JSON)
        fmt_score = next(s for s in scores if s.name == "format_compliance")
        assert fmt_score.score == 100.0

    def test_invalid_json(self):
        scores = evaluate_rule_based("not json", output_format=OutputFormat.JSON)
        fmt_score = next(s for s in scores if s.name == "format_compliance")
        assert fmt_score.score < 50

    def test_keyword_presence(self):
        scores = evaluate_rule_based("The summary includes analysis and results.",
                                     required_keywords=["summary", "analysis"])
        adh_score = next(s for s in scores if s.name == "instruction_adherence")
        assert adh_score.score == 100.0

    def test_keyword_missing(self):
        scores = evaluate_rule_based("Hello world.",
                                     required_keywords=["missing", "keyword"])
        adh_score = next(s for s in scores if s.name == "instruction_adherence")
        assert adh_score.score == 0.0

    def test_word_count_within(self):
        text = " ".join(["word"] * 50)
        scores = evaluate_rule_based(text, max_words=100)
        clarity = next(s for s in scores if s.name == "clarity")
        assert clarity.score >= 90

    def test_word_count_exceeded(self):
        text = " ".join(["word"] * 200)
        scores = evaluate_rule_based(text, max_words=50)
        clarity = next(s for s in scores if s.name == "clarity")
        assert clarity.score < 90

    def test_exact_match(self):
        scores = evaluate_rule_based("hello", expected_output="hello")
        acc = next(s for s in scores if s.name == "accuracy")
        assert acc.score == 100.0


class TestAggregateResults:
    def test_empty(self):
        result = aggregate_results([])
        assert result["total"] == 0
        assert result["avg_score"] == 0

    def test_with_results(self):
        results = [
            EvaluationResult(
                test_case_id="tc1", prompt_version_id="v1", experiment_id="e1",
                overall_score=80, execution_status=ExecutionStatus.SUCCESS,
            ),
            EvaluationResult(
                test_case_id="tc2", prompt_version_id="v1", experiment_id="e1",
                overall_score=90, execution_status=ExecutionStatus.SUCCESS,
            ),
        ]
        agg = aggregate_results(results)
        assert agg["total"] == 2
        assert agg["success"] == 2
        assert agg["avg_score"] == 85.0

    def test_with_failures(self):
        results = [
            EvaluationResult(
                test_case_id="tc1", prompt_version_id="v1", experiment_id="e1",
                overall_score=70, execution_status=ExecutionStatus.SUCCESS,
            ),
            EvaluationResult(
                test_case_id="tc2", prompt_version_id="v1", experiment_id="e1",
                overall_score=0, execution_status=ExecutionStatus.FAILED,
            ),
        ]
        agg = aggregate_results(results)
        assert agg["success"] == 1
        assert agg["failed"] == 1
        assert agg["avg_score"] == 70.0


class TestVerbosityPenaltyAndPairwiseJudge:
    def test_verbosity_penalty_applied_on_bloat(self):
        from src.llm_judge import apply_verbosity_penalty
        expected = "Yes, order 123 is shipped."  # 5 words
        # 60 words (bloated)
        bloated = "Indeed, upon careful inspection of the logistical database records and cross-referencing with carrier tracking manifests, I can affirmatively confirm without any shadow of ambiguity that your order designated with identifier 123 has indeed been formally dispatched from the regional sorting facility and is currently in active transit across designated transit corridors toward your destination address."
        penalized, notice = apply_verbosity_penalty(bloated, expected, base_score=95.0)
        assert penalized < 95.0
        assert notice is not None
        assert "Verbosity bias penalty applied" in notice

    def test_verbosity_penalty_not_applied_on_concise(self):
        from src.llm_judge import apply_verbosity_penalty
        expected = "Order 123 has been shipped."
        actual = "Your order 123 has shipped."
        score, notice = apply_verbosity_penalty(actual, expected, base_score=90.0)
        assert score == 90.0
        assert notice is None

    def test_pairwise_position_swap_demo(self):
        from src.llm_judge import evaluate_pairwise_position_swap
        from src.providers.demo_provider import DemoProvider
        provider = DemoProvider()
        res = evaluate_pairwise_position_swap(
            provider,
            instruction="Summarize feedback",
            input_data="Slow delivery",
            candidate_a="Delivery took 4 days.",
            candidate_b="Delayed shipping reported.",
        )
        assert "winner" in res
        assert "score_a" in res
        assert "score_b" in res
        assert res["position_bias_detected"] is False

    def test_concurrent_batch_evaluation_preserves_order(self):
        from src.evaluation_engine import evaluate_batch
        from src.schemas import PromptVersion, TestCase, EvaluationWeights, EvaluationMethod

        version = PromptVersion(
            experiment_id="e1",
            user_prompt_template="Echo: {{input}}",
        )
        test_cases = [
            TestCase(id=f"tc_{i}", input_data=f"Input message {i}", expected_output=f"Output {i}")
            for i in range(8)
        ]
        weights = EvaluationWeights(accuracy=1, relevance=1, instruction_adherence=1, clarity=1, format_compliance=1)

        progress_calls = []
        def _on_prog(cur, tot):
            progress_calls.append((cur, tot))

        results = evaluate_batch(
            version=version,
            test_cases=test_cases,
            experiment_id="e1",
            weights=weights,
            method=EvaluationMethod.RULE_BASED,
            max_workers=4,
            progress_callback=_on_prog,
        )

        assert len(results) == 8
        for i, res in enumerate(results):
            assert res.test_case_id == f"tc_{i}"
            assert res.input_data_snapshot == f"Input message {i}"
            assert res.expected_output_snapshot == f"Output {i}"
        assert len(progress_calls) == 8
