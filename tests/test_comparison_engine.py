"""
Shabd.Craft — Tests: Comparison Engine & Visual Diff
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.comparison_engine import build_word_diff_html, compare_versions


class TestWordDiffHtml:
    def test_highlights_insertions_and_deletions(self):
        html_out = build_word_diff_html("Summarize this text", "Summarize this feedback clearly")
        assert "line-through" in html_out
        assert "text" in html_out
        assert "feedback" in html_out
        assert "clearly" in html_out

    def test_escapes_html_tags_safely(self):
        html_out = build_word_diff_html("Input: {{x}}", "Input: <user_input>{{x}}</user_input>")
        assert "&lt;user_input&gt;" in html_out
        assert "<user_input>" not in html_out

    def test_identical_prompts_have_no_diff_spans(self):
        html_out = build_word_diff_html("Classify sentiment", "Classify sentiment")
        assert "line-through" not in html_out
        assert "#34d399" not in html_out


class TestCompareVersions:
    def test_clear_winner_b(self):
        va = {"id": "a", "version_label": "Original"}
        vb = {"id": "b", "version_label": "Candidate A"}
        ra = [{"execution_status": "success", "overall_score": 65.0, "criterion_scores": "[]"}]
        rb = [{"execution_status": "success", "overall_score": 85.0, "criterion_scores": "[]"}]
        comp = compare_versions(va, vb, ra, rb)
        assert comp.winner == "b"
        assert comp.version_b_overall == 85.0

