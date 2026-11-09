"""
Shabd.Craft — Tests: Prompt Optimizer
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch

from src.schemas import (
    PromptVersion, EvaluationResult, OptimizationCandidate,
    ExecutionStatus, PromptingTechnique, OutputFormat,
)
from src.optimizer import (
    generate_candidates, recommend_best,
    _parse_optimizer_response, _demo_candidates,
)


class TestDemoCandidates:
    def _make_version(self):
        return PromptVersion(
            experiment_id="exp-1",
            user_prompt_template="Summarize this: {{input_text}}",
            system_prompt="You are a summarizer.",
        )

    def test_generates_correct_count(self):
        version = self._make_version()
        candidates = _demo_candidates(version, "exp-1", 3, 70.0)
        assert len(candidates) == 3

    def test_generates_fewer_than_max(self):
        version = self._make_version()
        candidates = _demo_candidates(version, "exp-1", 2, 70.0)
        assert len(candidates) == 2

    def test_candidates_have_required_fields(self):
        version = self._make_version()
        candidates = _demo_candidates(version, "exp-1", 3, 70.0)
        for c in candidates:
            assert c.experiment_id == "exp-1"
            assert c.original_version_id == version.id
            assert c.candidate_label != ""
            assert c.strategy != ""
            assert c.user_prompt_template != ""
            assert c.changes_description != ""
            assert c.rationale != ""

    def test_candidates_are_deterministic(self):
        version = self._make_version()
        run1 = _demo_candidates(version, "exp-1", 3, 70.0)
        run2 = _demo_candidates(version, "exp-1", 3, 70.0)
        for c1, c2 in zip(run1, run2):
            assert c1.candidate_label == c2.candidate_label
            assert c1.user_prompt_template == c2.user_prompt_template

    def test_demo_label_in_changes(self):
        version = self._make_version()
        candidates = _demo_candidates(version, "exp-1", 3, 70.0)
        for c in candidates:
            assert "[DEMO]" in c.changes_description


class TestParseOptimizerResponse:
    def _make_version(self):
        return PromptVersion(
            experiment_id="exp-1",
            user_prompt_template="Original prompt",
        )

    def test_valid_json_response(self):
        import json
        version = self._make_version()
        payload = json.dumps({
            "candidates": [
                {
                    "label": "Candidate A",
                    "strategy": "Explicit Instructions",
                    "system_prompt": "Better system",
                    "user_prompt_template": "Better user prompt",
                    "changes_description": "Added clarity",
                    "rationale": "More explicit",
                }
            ]
        })
        candidates = _parse_optimizer_response(payload, version, "exp-1")
        assert len(candidates) == 1
        assert candidates[0].candidate_label == "Candidate A"
        assert candidates[0].strategy == "Explicit Instructions"

    def test_malformed_json_returns_empty(self):
        version = self._make_version()
        candidates = _parse_optimizer_response("not json at all", version, "exp-1")
        assert candidates == []

    def test_missing_candidates_key_returns_empty(self):
        version = self._make_version()
        candidates = _parse_optimizer_response('{"other": "data"}', version, "exp-1")
        assert candidates == []

    def test_json_embedded_in_text(self):
        import json
        version = self._make_version()
        payload_data = {
            "candidates": [
                {
                    "label": "Candidate B",
                    "strategy": "Task Decomposition",
                    "system_prompt": "Step-by-step sys",
                    "user_prompt_template": "Step-by-step user",
                    "changes_description": "Decomposed",
                    "rationale": "Clearer",
                }
            ]
        }
        content = f"Here is the result:\n{json.dumps(payload_data)}\nDone."
        candidates = _parse_optimizer_response(content, version, "exp-1")
        assert len(candidates) == 1
        assert candidates[0].candidate_label == "Candidate B"


class TestRecommendBest:
    def test_clear_winner(self):
        result = recommend_best(
            original_score=70.0,
            candidate_scores={"Candidate A": 85.0, "Candidate B": 75.0},
            test_case_count=10,
        )
        assert result["winner"] == "Candidate A"
        assert result["improvement"] is True
        assert result["best_score"] == 85.0

    def test_no_improvement(self):
        result = recommend_best(
            original_score=80.0,
            candidate_scores={"Candidate A": 75.0, "Candidate B": 72.0},
            test_case_count=10,
        )
        assert result["winner"] is None
        assert result["improvement"] is False

    def test_empty_candidates(self):
        result = recommend_best(
            original_score=70.0,
            candidate_scores={},
            test_case_count=5,
        )
        assert result["winner"] is None
        assert result["improvement"] is False

    def test_small_sample_size_warning(self):
        result = recommend_best(
            original_score=70.0,
            candidate_scores={"Candidate A": 85.0},
            test_case_count=3,
        )
        assert any("sample size" in lim.lower() for lim in result["limitations"])

    def test_small_score_diff_warning(self):
        result = recommend_best(
            original_score=70.0,
            candidate_scores={"Candidate A": 71.0},
            test_case_count=10,
        )
        assert any("noise" in lim.lower() or "small" in lim.lower() for lim in result["limitations"])

    def test_tie_score_no_winner(self):
        result = recommend_best(
            original_score=80.0,
            candidate_scores={"Candidate A": 80.0},
            test_case_count=10,
        )
        assert result["winner"] is None
        assert result["improvement"] is False


class TestGenerateCandidatesDemo:
    """Test generate_candidates in demo mode (no real API)."""

    def test_generates_candidates_demo_mode(self):
        version = PromptVersion(
            experiment_id="exp-1",
            user_prompt_template="Classify: {{text}}",
        )
        results = [
            EvaluationResult(
                test_case_id="tc1",
                prompt_version_id=version.id,
                experiment_id="exp-1",
                overall_score=65.0,
                execution_status=ExecutionStatus.SUCCESS,
            )
        ]

        with patch("src.optimizer.get_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.is_demo = True
            mock_get_provider.return_value = mock_provider

            candidates = generate_candidates(
                original_version=version,
                evaluation_results=results,
                experiment_id="exp-1",
                num_candidates=3,
            )

        assert len(candidates) == 3
        for c in candidates:
            assert isinstance(c, OptimizationCandidate)
            assert c.experiment_id == "exp-1"
