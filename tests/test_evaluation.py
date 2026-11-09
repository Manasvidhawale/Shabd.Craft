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
